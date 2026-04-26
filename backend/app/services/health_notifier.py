"""Health transition notifier.

Tracks the up/down state of operational resources (ML sidecar, FAISS index,
cameras, Redis) and emits admin notifications only on state transitions, with
a configurable boot-grace window to avoid deploy-time noise.

Safe to call from both async contexts and daemon threads (use the
*_threadsafe variants from threads). Notification emission failures are
caught and logged — they never propagate.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.database import SessionLocal
from app.services.notification_service import notify_admins

logger = logging.getLogger(__name__)

_BOOT_GRACE_SECONDS = 60.0
_states: dict[str, str] = {}
_boot_time: Optional[float] = None


def mark_boot() -> None:
    """Call once at application startup to begin the boot-grace window."""
    global _boot_time
    _boot_time = time.monotonic()


def _in_grace_period() -> bool:
    if _boot_time is None:
        return False
    return (time.monotonic() - _boot_time) < _BOOT_GRACE_SECONDS


async def report_health(
    resource: str,
    is_healthy: bool,
    *,
    down_title: str,
    down_message: str,
    down_type: str,
    recovered_title: Optional[str] = None,
    recovered_message: Optional[str] = None,
    recovered_type: Optional[str] = None,
    preference_key: str = "ml_health_alerts",
    reference_type: str = "system",
    reference_id: Optional[str] = None,
    send_email_on_down: bool = True,
    send_email_on_recovered: bool = False,
    down_severity: str = "error",
    recovered_severity: str = "info",
    dedup_window_seconds: int = 3600,
) -> None:
    """Emit a notification only when the resource transitions between states.

    Args:
        resource: Stable identifier (e.g. "ml_sidecar", "faiss", "camera:EB226").
        is_healthy: Current observed state.
        down_*: Notification fields used when transitioning healthy → unhealthy.
        recovered_*: Used when transitioning unhealthy → healthy.
            If recovered_title is None, no recovery notification is emitted.
    """
    if _in_grace_period():
        return

    new_state = "up" if is_healthy else "down"
    last_state = _states.get(resource)

    if last_state == new_state:
        return

    _states[resource] = new_state

    if new_state == "down":
        title, message, ntype = down_title, down_message, down_type
        severity = down_severity
        send_email = send_email_on_down
        toast_type = "error" if down_severity in ("error", "critical") else "warning"
    else:
        if recovered_title is None:
            return
        title = recovered_title
        message = recovered_message or recovered_title
        ntype = recovered_type or down_type
        severity = recovered_severity
        send_email = send_email_on_recovered
        toast_type = "success"

    try:
        # SessionLocal is sync. notify_admins is async but its DB calls are sync
        # under the hood (matches existing repo patterns).
        with SessionLocal() as db:
            await notify_admins(
                db,
                title,
                message,
                ntype,
                severity=severity,
                preference_key=preference_key,
                send_email=send_email,
                dedup_window_seconds=dedup_window_seconds,
                reference_id=reference_id or resource,
                reference_type=reference_type,
                toast_type=toast_type,
            )
    except Exception:
        logger.exception("health_notifier: failed to emit transition for %s", resource)


def report_health_threadsafe(
    loop: Optional[asyncio.AbstractEventLoop],
    **kwargs,
) -> None:
    """Schedule report_health on the given asyncio loop from a non-async thread.

    Used by FrameGrabber's daemon threads. Silently no-ops if no loop is
    available (e.g., during teardown). Never raises into the caller.
    """
    if loop is None or loop.is_closed():
        logger.debug("health_notifier: no event loop available for %s", kwargs.get("resource"))
        return
    try:
        asyncio.run_coroutine_threadsafe(report_health(**kwargs), loop)
    except Exception:
        logger.exception("health_notifier: run_coroutine_threadsafe failed")


async def emit_one_shot(
    *,
    title: str,
    message: str,
    notification_type: str,
    severity: str = "error",
    preference_key: str = "ml_health_alerts",
    reference_id: Optional[str] = None,
    reference_type: str = "system",
    send_email: bool = True,
    dedup_window_seconds: int = 1800,
    toast_type: str = "error",
) -> None:
    """One-shot emit (no transition tracking). Use for events that don't have a
    natural 'recovered' counterpart, e.g. FAISS mismatch detected this tick."""
    if _in_grace_period():
        return
    try:
        with SessionLocal() as db:
            await notify_admins(
                db,
                title,
                message,
                notification_type,
                severity=severity,
                preference_key=preference_key,
                send_email=send_email,
                dedup_window_seconds=dedup_window_seconds,
                reference_id=reference_id,
                reference_type=reference_type,
                toast_type=toast_type,
            )
    except Exception:
        logger.exception("health_notifier: one-shot emit failed for %s", notification_type)


def emit_one_shot_threadsafe(
    loop: Optional[asyncio.AbstractEventLoop],
    **kwargs,
) -> None:
    """Schedule emit_one_shot on the given asyncio loop from a non-async thread.

    Used by sync code paths (FrameGrabber stderr drain, redis client ping
    failure). Silently no-ops if no loop is available. Never raises.
    """
    if loop is None or loop.is_closed():
        logger.debug("health_notifier: no event loop available for one-shot %s", kwargs.get("notification_type"))
        return
    try:
        asyncio.run_coroutine_threadsafe(emit_one_shot(**kwargs), loop)
    except Exception:
        logger.exception("health_notifier: one-shot run_coroutine_threadsafe failed")
