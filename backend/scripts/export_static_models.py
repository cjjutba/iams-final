"""Re-export buffalo_l ONNX models with static input shapes.

Why this exists
---------------
``buffalo_l``'s SCRFD detector ships with **dynamic** input shapes. The
ONNX Runtime CoreML execution provider refuses to delegate dynamic-shape
graphs and silently falls back to CPU — which is why InsightFace is
pinned at ~1.5 fps on the M5 even with ``CoreMLExecutionProvider`` listed
first.

This script re-exports the SCRFD and ArcFace ONNX models with their input
shapes baked in (SCRFD → ``[1, 3, det_size, det_size]``,
ArcFace → ``[1, 3, 112, 112]``). With static shapes the EP can compile
the graph down to a CoreML mlmodel that runs on the Apple Neural Engine.
On M-series Macs the speedup is typically 5–10× for SCRFD-style models.

Usage
-----
::

    python -m scripts.export_static_models

The script is idempotent — if the output dir already contains both
re-exported ONNX files (and the sidecar matches the requested config), it
exits 0 without doing work. Safe to call from
``backend/entrypoint.sh`` on every container boot.

Operator verification
---------------------
After the next boot, watch the api-gateway logs for the per-model
provider lines added in
``backend/app/services/ml/insightface_model.py::load_model``:

::

    [insightface] detection (.../det_10g.onnx) → providers=['CoreMLExecutionProvider', ...]
    [insightface] recognition (.../w600k_r50.onnx) → providers=['CoreMLExecutionProvider', ...]

If either model still reports ``CPUExecutionProvider`` first, the
re-export did not take — diagnose before continuing the rollout.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("export_static_models")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# Default upstream cache dir InsightFace uses if INSIGHTFACE_HOME is unset.
DEFAULT_INSIGHTFACE_HOME = Path.home() / ".insightface"


@dataclass(frozen=True)
class ModelSpec:
    """One ONNX model to re-export with a fixed input shape.

    ``source_filename`` is what we read from the upstream pack; defaults
    to ``onnx_filename`` when not specified. Distinct field so the
    SCRFD-34G swap (Phase 4a) can read ``scrfd_34g.onnx`` while still
    writing the result out as ``det_10g.onnx`` — InsightFace's loader
    only looks for the canonical name, and we don't want to fork the
    loader.
    """

    onnx_filename: str
    input_name: str
    input_shape: tuple[int, int, int, int]  # (N, C, H, W)
    source_filename: str | None = None  # defaults to onnx_filename

    @property
    def src_name(self) -> str:
        return self.source_filename or self.onnx_filename


# SCRFD detector and ArcFace recognizer files inside ``buffalo_l``.
# ``input_name`` must match the actual input tensor name in the upstream
# ONNX. For buffalo_l these have been stable for years; if InsightFace
# changes them, the script will raise a clear error from
# ``update_inputs_outputs_dims``.
SCRFD_INPUT_NAME = "input.1"
ARCFACE_INPUT_NAME = "input.1"


def _resolve_models_root() -> Path:
    """Find ``~/.insightface/models`` (or honour ``INSIGHTFACE_HOME``)."""
    root_env = os.environ.get("INSIGHTFACE_HOME")
    root = Path(root_env) if root_env else DEFAULT_INSIGHTFACE_HOME
    return root / "models"


def _resolve_specs(det_size: int) -> list[tuple[str, ModelSpec]]:
    """Return [(model_pack_name, ModelSpec)] for the buffalo_l files we
    care about. ``model_pack_name`` is the source pack subdir under
    ``~/.insightface/models/``.

    SCRFD's input shape is read from ``det_size`` so the static export
    matches what ``FaceAnalysis.prepare()`` will request at runtime — the
    EP only delegates if the shape it sees at inference matches the
    shape baked into the graph.

    Detector swap (distant-face plan 2026-04-26 Phase 4a):
      The ``DETECTOR_ONNX_FILENAME`` env var picks which SCRFD variant
      to bake. ``det_10g.onnx`` (default, ships in buffalo_l) is the
      WIDER FACE Hard 83.05% baseline. ``scrfd_34g.onnx`` (the heavier
      sibling, +2.24 AP, ~2× wall-clock) must be downloaded separately
      from the InsightFace model zoo and dropped into
      ``~/.insightface/models/buffalo_l/scrfd_34g.onnx`` before
      re-running this script.

      The script writes the chosen variant out as ``det_10g.onnx``
      regardless inside the static pack, so the InsightFace loader
      finds it under the canonical name. (Renaming the bake
      file-stem would require also patching FaceAnalysis's loader,
      which we don't want to do.) The sidecar's /health response
      includes the providers list per task — that's how an operator
      verifies the swap took effect.
    """
    detector_source = os.environ.get("DETECTOR_ONNX_FILENAME", "det_10g.onnx")
    return [
        (
            "buffalo_l",
            ModelSpec(
                # Always write as det_10g.onnx — that's the filename
                # InsightFace's FaceAnalysis loader looks for. When
                # DETECTOR_ONNX_FILENAME != det_10g.onnx (e.g. the
                # 34G swap), we copy that source onto disk under the
                # canonical name so the loader picks it up
                # transparently.
                onnx_filename="det_10g.onnx",
                input_name=SCRFD_INPUT_NAME,
                input_shape=(1, 3, det_size, det_size),
                source_filename=detector_source,
            ),
        ),
        (
            "buffalo_l",
            ModelSpec(
                onnx_filename="w600k_r50.onnx",
                input_name=ARCFACE_INPUT_NAME,
                input_shape=(1, 3, 112, 112),
            ),
        ),
    ]


def _sidecar_path(out_dir: Path) -> Path:
    return out_dir / "static_export.json"


def _read_sidecar(out_dir: Path) -> dict | None:
    p = _sidecar_path(out_dir)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _write_sidecar(out_dir: Path, payload: dict) -> None:
    _sidecar_path(out_dir).write_text(json.dumps(payload, indent=2))


def _export_one(src_onnx: Path, dst_onnx: Path, spec: ModelSpec) -> None:
    """Bake static input shape into ``src_onnx`` and write to ``dst_onnx``.

    Uses ``onnx.tools.update_model_dims.update_inputs_outputs_dims`` for
    the dim update, then ``onnxsim.simplify`` to fold any constant ops
    that became foldable once the shape was concrete (this is what makes
    the CoreML EP happy — dynamic ``Reshape``/``Resize`` ops in the
    upstream ONNX disappear after simplification).
    """
    import onnx
    from onnx.tools import update_model_dims

    logger.info("Loading %s", src_onnx)
    model = onnx.load(str(src_onnx))

    # Determine the model's own input name — defensive: if the upstream
    # ONNX renames the input, ``update_inputs_outputs_dims`` raises a
    # KeyError that's noisier than the explicit check below.
    actual_input_names = [i.name for i in model.graph.input]
    if spec.input_name not in actual_input_names:
        if len(actual_input_names) == 1:
            logger.warning(
                "Expected input '%s' in %s, got '%s'; using detected name",
                spec.input_name,
                spec.onnx_filename,
                actual_input_names[0],
            )
            input_name = actual_input_names[0]
        else:
            raise RuntimeError(
                f"Cannot resolve input name for {spec.onnx_filename}: "
                f"expected '{spec.input_name}', found {actual_input_names}"
            )
    else:
        input_name = spec.input_name

    output_names = [o.name for o in model.graph.output]
    n, c, h, w = spec.input_shape
    logger.info(
        "Pinning %s input '%s' to shape (%d, %d, %d, %d)",
        spec.onnx_filename,
        input_name,
        n,
        c,
        h,
        w,
    )
    model = update_model_dims.update_inputs_outputs_dims(
        model,
        {input_name: [n, c, h, w]},
        # Outputs left as-is — they remain dynamic (e.g. variable
        # detection counts). CoreML only requires fixed *inputs* to
        # delegate; outputs can stay symbolic.
        {name: ["?"] * len(model.graph.output[idx].type.tensor_type.shape.dim) for idx, name in enumerate(output_names)},
    )

    try:
        from onnxsim import simplify

        logger.info("Simplifying %s with onnxsim", spec.onnx_filename)
        model_simplified, ok = simplify(model)
        if not ok:
            logger.warning("onnxsim could not validate %s; using unsimplified static model", spec.onnx_filename)
        else:
            model = model_simplified
    except ImportError:
        logger.warning("onnxsim not installed; skipping simplification (CoreML may still reject the graph)")

    dst_onnx.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, str(dst_onnx))
    logger.info("Wrote %s", dst_onnx)


def export(det_size: int, out_subdir: str = "buffalo_l_static") -> Path:
    """Re-export the buffalo_l ONNX models with static shapes.

    Returns the output directory containing the static-shape files. The
    directory is laid out the same way as upstream so we can point
    ``FaceAnalysis(name=...)`` at ``buffalo_l_static`` and have it find
    ``det_10g.onnx`` / ``w600k_r50.onnx`` without further changes.
    """
    models_root = _resolve_models_root()
    out_dir = models_root / out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    requested = {
        "det_size": det_size,
        "specs": [
            {"file": s.onnx_filename, "shape": list(s.input_shape)} for _, s in _resolve_specs(det_size)
        ],
    }
    existing = _read_sidecar(out_dir)
    if existing == requested and all(
        (out_dir / s.onnx_filename).exists() for _, s in _resolve_specs(det_size)
    ):
        logger.info("Static export already present and matches request — skipping")
        return out_dir

    # Export each model (or, for ArcFace where the input is already fixed,
    # just copy + re-validate).
    for pack_name, spec in _resolve_specs(det_size):
        src = models_root / pack_name / spec.src_name
        dst = out_dir / spec.onnx_filename
        if not src.exists():
            # Phase 4a: SCRFD-34G isn't part of the buffalo_l zip — the
            # operator must download it manually. Surface a more
            # actionable error in that case.
            if spec.src_name != spec.onnx_filename:
                raise FileNotFoundError(
                    f"DETECTOR_ONNX_FILENAME={spec.src_name!r} is set, but "
                    f"{src} is missing. Download the SCRFD-34G ONNX from "
                    f"the InsightFace model zoo "
                    f"(https://github.com/deepinsight/insightface/tree/master/detection/scrfd) "
                    f"and place it under {src.parent} before re-running."
                )
            raise FileNotFoundError(
                f"Source ONNX missing: {src}. Has InsightFace downloaded the "
                f"buffalo_l pack on this machine yet?"
            )
        _export_one(src, dst, spec)

    # Copy any auxiliary files buffalo_l ships (the ``models`` keyword
    # in InsightFace also reads landmark / genderage ONNX, but our
    # ``allowed_modules=['detection', 'recognition']`` config skips them
    # — copying everything keeps the static dir parity-clean and means
    # an operator can flip ``allowed_modules`` later without re-export).
    src_pack = models_root / "buffalo_l"
    if src_pack.exists():
        for child in src_pack.iterdir():
            dst = out_dir / child.name
            if dst.exists():
                continue
            if child.is_file():
                shutil.copy2(child, dst)
                logger.debug("Copied auxiliary file %s", child.name)

    _write_sidecar(out_dir, requested)
    logger.info("Static export complete → %s", out_dir)
    return out_dir


def main() -> int:
    det_size_env = os.environ.get("INSIGHTFACE_DET_SIZE", "640")
    try:
        det_size = int(det_size_env)
    except ValueError:
        logger.error("INSIGHTFACE_DET_SIZE must be an integer, got %r", det_size_env)
        return 2

    out_subdir = os.environ.get("INSIGHTFACE_STATIC_PACK_NAME", "buffalo_l_static")

    try:
        out_dir = export(det_size=det_size, out_subdir=out_subdir)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 3
    except Exception:
        logger.exception("Static export failed")
        return 1

    print(str(out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
