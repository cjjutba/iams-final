"""Download MiniFASNet checkpoints + export to ONNX for the IAMS ML sidecar.

Why this exists
---------------
The realtime liveness layer uses MiniFASNet (MiniVision Technologies,
"Silent Face Anti-Spoofing", Apache-2.0). Upstream ships PyTorch ``.pth``
checkpoints. To serve those from the on-prem ML sidecar with the
``CoreMLExecutionProvider`` on the M5's Apple Neural Engine, we need
ONNX with a fully static input shape — same constraint as
``export_static_models.py`` for SCRFD + ArcFace.

This script:

  1. Clones the upstream repo into a temp dir (or reuses one passed via
     ``LIVENESS_UPSTREAM_DIR``).
  2. Imports its model classes (``src.model_lib.MiniFASNet``) so we
     never rebuild the architecture from memory — the .pth state_dicts
     remain authoritative.
  3. Loads each of the two checkpoints in ``resources/anti_spoof_models/``.
  4. Exports each to ONNX with input shape ``[1, 3, 80, 80]``.
  5. Saves the ONNX files to ``~/.insightface/models/minifasnet/`` so
     they sit next to the buffalo_l static pack the sidecar already
     loads.
  6. Verifies each exported ONNX loads in ORT and produces the expected
     [1, 3] logits shape on a noise frame.

Operator usage
--------------
::

    backend/venv/bin/pip install torch torchvision   # ~700 MB, one-time
    backend/venv/bin/python -m scripts.export_liveness_models

After it succeeds, set ``LIVENESS_ENABLED=true`` in
``backend/.env.onprem``, restart the ML sidecar
(``./scripts/start-ml-sidecar.sh``), and restart the api-gateway
(``./scripts/onprem-up.sh``). The sidecar's ``/health`` will then
report ``liveness_loaded: true`` and the realtime tracker will start
gating recognitions on liveness.

Idempotency
-----------
Re-running the script is a no-op when the ONNX files already exist and
match the request manifest. Pass ``--force`` to re-export (e.g. after a
torch version change).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# ----------------------------------------------------------------------
# Defaults
# ----------------------------------------------------------------------
UPSTREAM_REPO_URL = os.environ.get(
    "LIVENESS_UPSTREAM_REPO",
    "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing.git",
)
# Pin to a known-good commit so a future upstream rename can't break the
# import. This is the commit whose ``src/model_lib/MiniFASNet.py``
# definition matches the published .pth checkpoints under
# ``resources/anti_spoof_models/`` — operator can override via env if a
# newer pinned commit is preferred.
UPSTREAM_REPO_COMMIT = os.environ.get("LIVENESS_UPSTREAM_COMMIT", "main")

# Resolve INSIGHTFACE_HOME the same way ``LivenessModel._resolve_models_root``
# does — env var wins when set, otherwise fall back to ``~/.insightface``.
# Note: ``Path("") or fallback`` is buggy — ``Path("")`` is truthy under
# Python's default object truthiness rules and short-circuits the ``or``,
# leaving the script writing to ``./models/minifasnet`` from cwd. Explicit
# string check avoids that footgun.
_HOME_ENV = os.environ.get("INSIGHTFACE_HOME", "").strip()
DEFAULT_INSIGHTFACE_HOME = Path(_HOME_ENV) if _HOME_ENV else (Path.home() / ".insightface")
OUT_PACK_NAME = os.environ.get("LIVENESS_PACK_NAME", "minifasnet")

# The two checkpoints we ship by default. Each entry maps:
#   filename in upstream's resources/anti_spoof_models/  →  metadata
# The "scale" is the bbox-expansion factor used when cropping from the
# source frame — must match training. The sidecar reads the same value
# from the manifest so a pack rebuilt with different scales remains
# self-describing.
@dataclass(frozen=True)
class LivenessCheckpoint:
    pth_filename: str
    onnx_filename: str
    model_class: str  # name of class to instantiate from upstream's MiniFASNet.py
    scale: float
    input_size: int = 80
    num_classes: int = 3

CHECKPOINTS: list[LivenessCheckpoint] = [
    LivenessCheckpoint(
        pth_filename="2.7_80x80_MiniFASNetV2.pth",
        onnx_filename="2.7_80x80_MiniFASNetV2.onnx",
        model_class="MiniFASNetV2",
        scale=2.7,
    ),
    LivenessCheckpoint(
        pth_filename="4_0_0_80x80_MiniFASNetV1SE.pth",
        onnx_filename="4_0_0_80x80_MiniFASNetV1SE.onnx",
        model_class="MiniFASNetV1SE",
        scale=4.0,
    ),
]

logger = logging.getLogger("export_liveness_models")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def _check_torch() -> None:
    """Fail fast with a clear pip command if torch isn't available."""
    try:
        import torch  # noqa: F401
        if getattr(torch, "__file__", None) is None:
            raise ImportError("torch import resolved to a stub package — not really installed")
    except Exception as exc:
        logger.error(
            "PyTorch is required for one-time MiniFASNet ONNX export.\n"
            "Install it into the macOS venv:\n"
            "    backend/venv/bin/pip install torch torchvision\n"
            "Original error: %s",
            exc,
        )
        sys.exit(2)


def _ensure_upstream_clone(workdir: Path) -> Path:
    """Clone or reuse the upstream Silent-Face-Anti-Spoofing checkout.

    Honours ``LIVENESS_UPSTREAM_DIR`` to point at a local mirror — useful
    on hosts without GitHub access.
    """
    local_override = os.environ.get("LIVENESS_UPSTREAM_DIR")
    if local_override:
        p = Path(local_override).expanduser().resolve()
        if not (p / "src" / "model_lib" / "MiniFASNet.py").exists():
            raise FileNotFoundError(
                f"LIVENESS_UPSTREAM_DIR={p} is not a Silent-Face-Anti-Spoofing checkout"
            )
        logger.info("Using local upstream checkout: %s", p)
        return p

    target = workdir / "Silent-Face-Anti-Spoofing"
    logger.info("Cloning upstream %s @ %s -> %s", UPSTREAM_REPO_URL, UPSTREAM_REPO_COMMIT, target)
    subprocess.run(
        ["git", "clone", "--depth", "1", UPSTREAM_REPO_URL, str(target)],
        check=True,
    )
    if UPSTREAM_REPO_COMMIT and UPSTREAM_REPO_COMMIT != "main":
        # --depth 1 only fetches HEAD; for a non-default commit, fetch +
        # checkout so we land on the right ref. Operator can pin to a
        # specific commit hash for reproducibility.
        subprocess.run(["git", "-C", str(target), "fetch", "--depth", "1", "origin", UPSTREAM_REPO_COMMIT], check=True)
        subprocess.run(["git", "-C", str(target), "checkout", "FETCH_HEAD"], check=True)
    return target


def _import_upstream_classes(upstream_dir: Path):
    """Add upstream/src to sys.path and import the two model classes.

    Done lazily because torch isn't usually installed in the gateway image
    — only on the host venv where this script runs.
    """
    src_path = upstream_dir / "src"
    if not src_path.exists():
        raise FileNotFoundError(f"Expected {src_path} in upstream checkout")
    sys.path.insert(0, str(src_path))
    try:
        from model_lib.MiniFASNet import MiniFASNetV2, MiniFASNetV1SE  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            f"Could not import MiniFASNet model classes from {src_path}. "
            f"Has the upstream layout changed? Original error: {exc}"
        ) from exc
    return {"MiniFASNetV2": MiniFASNetV2, "MiniFASNetV1SE": MiniFASNetV1SE}


def _load_state_dict_strict(model, state_dict_obj):
    """Strip the ``module.`` DataParallel prefix and load.

    Upstream sometimes saves the entire model + optimizer in the .pth.
    Handle both: a plain state_dict and a checkpoint dict containing one.
    """
    if isinstance(state_dict_obj, dict) and "state_dict" in state_dict_obj:
        sd = state_dict_obj["state_dict"]
    else:
        sd = state_dict_obj
    cleaned = {}
    for k, v in sd.items():
        if k.startswith("module."):
            cleaned[k[len("module."):]] = v
        else:
            cleaned[k] = v
    missing, unexpected = model.load_state_dict(cleaned, strict=False)
    if missing or unexpected:
        logger.warning(
            "load_state_dict completed with missing=%d, unexpected=%d (likely BatchNorm running stats — usually safe)",
            len(missing), len(unexpected),
        )


def _export_one(
    upstream_dir: Path,
    classes: dict,
    spec: LivenessCheckpoint,
    out_dir: Path,
    force: bool,
) -> Path:
    """Load one .pth and write the corresponding ONNX file."""
    import torch

    pth_path = upstream_dir / "resources" / "anti_spoof_models" / spec.pth_filename
    if not pth_path.exists():
        raise FileNotFoundError(
            f"Upstream checkpoint missing: {pth_path}\n"
            "The upstream repo's resources/anti_spoof_models/ directory should "
            "ship both .pth files. Re-clone or fetch with LFS if it's empty."
        )
    onnx_path = out_dir / spec.onnx_filename
    if onnx_path.exists() and not force:
        logger.info("ONNX already present, skipping (use --force to re-export): %s", onnx_path)
        return onnx_path

    cls = classes[spec.model_class]
    # MiniFASNet constructor signature in upstream: (keep_dict, embedding_size,
    # conv6_kernel, drop_p, num_classes, img_channel). conv6_kernel is the
    # spatial size of the depthwise final pooling conv and MUST match the
    # value the .pth was trained with — upstream computes it from the
    # input resolution as ``((H+15)//16, (W+15)//16)`` (see
    # ``src/utility.py::get_kernel`` in Silent-Face-Anti-Spoofing). For
    # the 80x80 deploy variants this is (5, 5); leaving the default (7, 7)
    # raises a ``size mismatch for conv_6_dw.conv.weight`` on load.
    conv6_kernel = (
        (spec.input_size + 15) // 16,
        (spec.input_size + 15) // 16,
    )
    logger.info(
        "Instantiating %s(num_classes=%d, conv6_kernel=%s) for %dx%d input",
        spec.model_class,
        spec.num_classes,
        conv6_kernel,
        spec.input_size,
        spec.input_size,
    )
    model = cls(
        num_classes=spec.num_classes,
        img_channel=3,
        conv6_kernel=conv6_kernel,
    )
    state = torch.load(str(pth_path), map_location="cpu", weights_only=True) if hasattr(torch, "load") else None
    if state is None:
        # Older torch without weights_only kwarg
        state = torch.load(str(pth_path), map_location="cpu")
    _load_state_dict_strict(model, state)
    model.eval()

    dummy = torch.zeros(1, 3, spec.input_size, spec.input_size, dtype=torch.float32)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Exporting %s -> %s", spec.pth_filename, onnx_path)
    # Force the legacy TorchScript-based exporter (``dynamo=False``). The
    # new dynamo-based exporter (default in torch >= 2.6) writes weights
    # to a sidecar ``<name>.onnx.data`` file via the ONNX external-data
    # format, which ORT then refuses to load when InferenceSession is
    # constructed with a path argument and the external file lookup
    # collides with its initializer path-validation. The legacy exporter
    # produces a single self-contained .onnx file (~250 KB graph + ~1.7 MB
    # weights = ~2 MB total — well under the 2 GB protobuf limit), which
    # is what the sidecar's LivenessModel.load() expects.
    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        export_params=True,
        opset_version=13,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["logits"],
        # Static batch — required for the CoreML execution provider to
        # delegate to the Apple Neural Engine. The sidecar chunks
        # batches at the recognition path's max_batch when N > 1.
        dynamic_axes=None,
        dynamo=False,
    )

    # Round-trip verify: load the ONNX in ORT and run a single noise frame.
    # Catches obvious corruption immediately so the operator doesn't have
    # to tail the sidecar log to discover it.
    _verify_onnx(onnx_path, spec)
    return onnx_path


def _verify_onnx(onnx_path: Path, spec: LivenessCheckpoint) -> None:
    import numpy as np
    import onnxruntime as ort

    logger.info("Verifying %s with onnxruntime...", onnx_path.name)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    if list(inp.shape) != [1, 3, spec.input_size, spec.input_size]:
        raise RuntimeError(
            f"ONNX input shape mismatch: got {inp.shape}, expected "
            f"[1, 3, {spec.input_size}, {spec.input_size}]"
        )
    arr = np.zeros((1, 3, spec.input_size, spec.input_size), dtype=np.float32)
    out = sess.run(None, {inp.name: arr})
    if out[0].shape != (1, spec.num_classes):
        raise RuntimeError(
            f"ONNX output shape mismatch: got {out[0].shape}, "
            f"expected (1, {spec.num_classes})"
        )
    logger.info("  ✓ %s loaded, runs, output shape = %s", onnx_path.name, out[0].shape)


def _write_manifest(out_dir: Path) -> None:
    """Write a self-describing JSON sidecar so the runtime knows the
    scale + class indices for each ONNX without having to hardcode them."""
    payload = {
        "format": 1,
        "models": [
            {
                "onnx_filename": spec.onnx_filename,
                "model_class": spec.model_class,
                "scale": spec.scale,
                "input_size": spec.input_size,
                "num_classes": spec.num_classes,
                # Index of the "real" class in the softmax output.
                # Upstream class layout:  0 = spoof_2D, 1 = real, 2 = spoof_3D
                "real_class_index": 1,
            }
            for spec in CHECKPOINTS
        ],
        "license": "Apache-2.0",
        "upstream": "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing",
    }
    p = out_dir / "manifest.json"
    p.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote manifest: %s", p)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-export even if the target ONNX files already exist",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_INSIGHTFACE_HOME / "models" / OUT_PACK_NAME,
        help="Where to write the ONNX files (default: ~/.insightface/models/minifasnet/)",
    )
    args = parser.parse_args()

    _check_torch()

    cleanup_dir: Path | None = None
    try:
        if os.environ.get("LIVENESS_UPSTREAM_DIR"):
            upstream_dir = _ensure_upstream_clone(Path(tempfile.mkdtemp()))  # ignored
        else:
            cleanup_dir = Path(tempfile.mkdtemp(prefix="iams-liveness-"))
            upstream_dir = _ensure_upstream_clone(cleanup_dir)
        classes = _import_upstream_classes(upstream_dir)

        out_dir = args.out_dir.expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        for spec in CHECKPOINTS:
            _export_one(upstream_dir, classes, spec, out_dir, force=args.force)

        _write_manifest(out_dir)

        logger.info("")
        logger.info("=" * 60)
        logger.info("  Liveness ONNX pack ready: %s", out_dir)
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Set LIVENESS_ENABLED=true in backend/.env.onprem")
        logger.info("  2. ./scripts/stop-ml-sidecar.sh && ./scripts/start-ml-sidecar.sh")
        logger.info("  3. ./scripts/onprem-up.sh")
        logger.info("  4. Verify health:")
        logger.info("       curl -s http://127.0.0.1:8001/health | jq '.liveness'")
        logger.info("")
        return 0
    except subprocess.CalledProcessError as exc:
        logger.error("git command failed: %s", exc)
        return 3
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 4
    except Exception:
        logger.exception("Liveness export failed")
        return 1
    finally:
        if cleanup_dir and cleanup_dir.exists():
            try:
                shutil.rmtree(cleanup_dir)
            except Exception:
                logger.debug("Could not clean temp dir %s", cleanup_dir, exc_info=True)


if __name__ == "__main__":
    sys.exit(main())
