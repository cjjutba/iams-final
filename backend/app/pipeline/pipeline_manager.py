"""Pipeline lifecycle manager -- starts, stops, and monitors video pipelines.

Each pipeline runs as a separate ``multiprocessing.Process`` for CPU isolation
from the FastAPI event loop.  Communication between FastAPI and the pipeline
processes happens exclusively through Redis (state publishing + commands).
"""

import multiprocessing
import time

from app.config import logger, settings


def _run_pipeline_process(config: dict, redis_url: str) -> None:
    """Entry point for the pipeline subprocess.

    Imports are deferred so that ML models are loaded only inside the child
    process, avoiding double-loading in the FastAPI parent.

    Args:
        config: Pipeline configuration dict (passed to VideoAnalyticsPipeline).
        redis_url: Redis connection URL for state publishing.
    """
    import redis as redis_lib

    from app.pipeline.video_pipeline import VideoAnalyticsPipeline

    pipeline = VideoAnalyticsPipeline(config)
    pipeline._redis = redis_lib.Redis.from_url(redis_url)

    try:
        pipeline.start()  # Blocking loop
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"[Pipeline:{config['room_id']}] Crashed: {e}")
    finally:
        pipeline.stop()


class PipelineManager:
    """Manages video pipeline processes for all active rooms.

    Each room gets its own ``multiprocessing.Process`` running a
    ``VideoAnalyticsPipeline``.  The manager handles start/stop/restart and
    provides a health check method for the FastAPI health endpoint.

    Args:
        redis_url: Redis connection URL passed to child processes.
    """

    def __init__(self, redis_url: str | None = None) -> None:
        self._pipelines: dict[str, dict] = {}
        self._redis_url = redis_url or settings.REDIS_URL

    def start_pipeline(self, config: dict) -> None:
        """Start a pipeline process for a room.

        If a pipeline for the given ``room_id`` is already running, this is a
        no-op.  If the previous process died, it is cleaned up first.

        Args:
            config: Pipeline configuration dict.  Must contain ``room_id``.
        """
        room_id = config["room_id"]

        if room_id in self._pipelines:
            proc = self._pipelines[room_id]["process"]
            if proc.is_alive():
                logger.warning(f"Pipeline for {room_id} already running")
                return
            # Dead process -- clean up and restart
            self._pipelines.pop(room_id)

        proc = multiprocessing.Process(
            target=_run_pipeline_process,
            args=(config, self._redis_url),
            daemon=True,
            name=f"pipeline-{room_id}",
        )
        proc.start()
        self._pipelines[room_id] = {"process": proc, "config": config}
        logger.info(f"Pipeline for {room_id} started (PID {proc.pid})")

    def stop_pipeline(self, room_id: str) -> None:
        """Stop a pipeline process for a room.

        Gracefully terminates the process with ``SIGTERM``, then ``SIGKILL``
        if it doesn't exit within 10 seconds.

        Args:
            room_id: Room identifier.
        """
        entry = self._pipelines.pop(room_id, None)
        if entry is None:
            return

        proc = entry["process"]
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=10)
            if proc.is_alive():
                proc.kill()
        logger.info(f"Pipeline for {room_id} stopped")

    def stop_all(self) -> None:
        """Stop all running pipeline processes."""
        for room_id in list(self._pipelines.keys()):
            self.stop_pipeline(room_id)

    def get_status(self) -> list[dict]:
        """Get status of all managed pipelines.

        Returns:
            List of dicts with ``room_id``, ``alive``, and ``pid`` keys.
        """
        result = []
        for room_id, entry in self._pipelines.items():
            proc = entry["process"]
            result.append({
                "room_id": room_id,
                "alive": proc.is_alive(),
                "pid": proc.pid,
            })
        return result

    def check_health(self) -> None:
        """Restart any dead pipeline processes.

        Iterates over all managed pipelines and restarts any whose process
        has exited.  Intended to be called periodically (e.g. every 30 s)
        from a background scheduler.
        """
        for room_id, entry in list(self._pipelines.items()):
            proc = entry["process"]
            if not proc.is_alive():
                logger.warning(f"Pipeline for {room_id} died, restarting...")
                self._pipelines.pop(room_id)
                self.start_pipeline(entry["config"])
