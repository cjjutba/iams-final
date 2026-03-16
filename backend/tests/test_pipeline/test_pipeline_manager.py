"""Tests for PipelineManager -- manages pipeline lifecycle."""

from unittest.mock import MagicMock, patch

import pytest


class TestPipelineManager:
    def test_start_pipeline_creates_process(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        with patch("app.pipeline.pipeline_manager.multiprocessing") as mock_mp:
            mock_proc = MagicMock()
            mock_mp.Process.return_value = mock_proc

            mgr.start_pipeline({
                "room_id": "room-1",
                "rtsp_source": "rtsp://mediamtx:8554/room-1/raw",
                "rtsp_target": "rtsp://mediamtx:8554/room-1/annotated",
                "width": 640, "height": 480, "fps": 25,
                "room_name": "R301", "det_model": "buffalo_sc",
            })
            assert "room-1" in mgr._pipelines
            mock_proc.start.assert_called_once()

    def test_stop_pipeline_terminates_process(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        mock_proc = MagicMock()
        mock_proc.is_alive.return_value = True
        mgr._pipelines["room-1"] = {"process": mock_proc, "config": {}}

        mgr.stop_pipeline("room-1")
        mock_proc.terminate.assert_called_once()
        assert "room-1" not in mgr._pipelines

    def test_stop_nonexistent_pipeline_is_noop(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        mgr.stop_pipeline("nonexistent")  # Should not raise

    def test_get_status_returns_all_pipelines(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        mock_proc = MagicMock()
        mock_proc.is_alive.return_value = True
        mock_proc.pid = 12345
        mgr._pipelines["room-1"] = {
            "process": mock_proc,
            "config": {"room_id": "room-1"},
        }

        status = mgr.get_status()
        assert len(status) == 1
        assert status[0]["room_id"] == "room-1"
        assert status[0]["alive"] is True
        assert status[0]["pid"] == 12345

    def test_stop_all_stops_every_pipeline(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        for rid in ["room-1", "room-2", "room-3"]:
            mock_proc = MagicMock()
            mock_proc.is_alive.return_value = True
            mgr._pipelines[rid] = {"process": mock_proc, "config": {"room_id": rid}}

        mgr.stop_all()
        assert len(mgr._pipelines) == 0

    def test_start_pipeline_skips_if_already_running(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        mock_proc = MagicMock()
        mock_proc.is_alive.return_value = True
        mgr._pipelines["room-1"] = {
            "process": mock_proc,
            "config": {"room_id": "room-1"},
        }

        with patch("app.pipeline.pipeline_manager.multiprocessing") as mock_mp:
            mgr.start_pipeline({"room_id": "room-1"})
            # Should NOT create a new process
            mock_mp.Process.assert_not_called()

    def test_check_health_restarts_dead_pipeline(self):
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        mock_proc = MagicMock()
        mock_proc.is_alive.return_value = False  # Dead
        config = {
            "room_id": "room-1",
            "rtsp_source": "x",
            "rtsp_target": "x",
            "width": 640, "height": 480, "fps": 25,
            "room_name": "R", "det_model": "buffalo_sc",
        }
        mgr._pipelines["room-1"] = {"process": mock_proc, "config": config}

        with patch("app.pipeline.pipeline_manager.multiprocessing") as mock_mp:
            new_proc = MagicMock()
            mock_mp.Process.return_value = new_proc

            mgr.check_health()
            # A new process should have been created
            mock_mp.Process.assert_called_once()
            new_proc.start.assert_called_once()
            assert "room-1" in mgr._pipelines

    def test_start_pipeline_replaces_dead_process(self):
        """If the previous process died, start_pipeline should replace it."""
        from app.pipeline.pipeline_manager import PipelineManager

        mgr = PipelineManager()
        dead_proc = MagicMock()
        dead_proc.is_alive.return_value = False  # Dead
        mgr._pipelines["room-1"] = {"process": dead_proc, "config": {"room_id": "room-1"}}

        with patch("app.pipeline.pipeline_manager.multiprocessing") as mock_mp:
            new_proc = MagicMock()
            mock_mp.Process.return_value = new_proc

            mgr.start_pipeline({
                "room_id": "room-1",
                "rtsp_source": "x", "rtsp_target": "x",
                "width": 640, "height": 480, "fps": 25,
                "room_name": "R", "det_model": "buffalo_sc",
            })
            mock_mp.Process.assert_called_once()
            new_proc.start.assert_called_once()
