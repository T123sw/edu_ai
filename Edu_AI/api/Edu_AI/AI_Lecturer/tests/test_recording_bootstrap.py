import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np


MODULE_ROOT = Path(__file__).resolve().parents[1] / "LiveTalking-main"
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from avatars.base_avatar import BaseAvatar  # noqa: E402


class _FakeStdin:
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    def close(self):
        self.closed = True


class _FakeProcess:
    def __init__(self, command):
        self.command = command
        self.stdin = _FakeStdin()
        self.wait_called = False

    def wait(self):
        self.wait_called = True


def _build_avatar(frame_list_cycle=None):
    avatar = object.__new__(BaseAvatar)
    avatar.opt = SimpleNamespace(sessionid=123)
    avatar.recording = False
    avatar.recording_requested = False
    avatar._record_video_pipe = None
    avatar._record_audio_pipe = None
    avatar._recording_paths = None
    avatar.width = 0
    avatar.height = 0
    avatar.frame_list_cycle = frame_list_cycle if frame_list_cycle is not None else []
    return avatar


class RecordingBootstrapTests(unittest.TestCase):
    @staticmethod
    def _video_size_arg(command):
        return command[command.index("-s") + 1]

    def test_start_recording_uses_avatar_frame_size_when_dimensions_are_unset(self):
        avatar = _build_avatar(
            [np.zeros((480, 640, 3), dtype=np.uint8)]
        )
        processes = []

        def fake_popen(command, **kwargs):
            process = _FakeProcess(command)
            processes.append(process)
            return process

        with patch("avatars.base_avatar.recording_paths_for_session") as mock_paths, patch(
            "avatars.base_avatar.subprocess.Popen",
            side_effect=fake_popen,
        ):
            mock_paths.return_value = SimpleNamespace(
                video="video.mp4",
                audio="audio.aac",
                final="final.mp4",
            )

            avatar.start_recording()

        self.assertEqual(avatar.width, 640)
        self.assertEqual(avatar.height, 480)
        self.assertEqual(self._video_size_arg(processes[0].command), "640x480")

    def test_start_recording_waits_for_first_frame_when_avatar_size_is_unknown(self):
        avatar = _build_avatar()
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        processes = []

        def fake_popen(command, **kwargs):
            process = _FakeProcess(command)
            processes.append(process)
            return process

        with patch("avatars.base_avatar.recording_paths_for_session") as mock_paths, patch(
            "avatars.base_avatar.subprocess.Popen",
            side_effect=fake_popen,
        ):
            mock_paths.return_value = SimpleNamespace(
                video="video.mp4",
                audio="audio.aac",
                final="final.mp4",
            )

            avatar.start_recording()
            self.assertEqual(len(processes), 0)
            avatar.record_video_data(frame)

        self.assertEqual(len(processes), 2)
        self.assertEqual(self._video_size_arg(processes[0].command), "640x360")
        self.assertTrue(processes[0].stdin.writes)


if __name__ == "__main__":
    unittest.main()
