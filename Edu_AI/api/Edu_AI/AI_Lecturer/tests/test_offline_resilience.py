import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OfflineResilienceTests(unittest.TestCase):
    def test_wav2lip_offline_uses_low_memory_defaults(self):
        source = (ROOT / "offline_video_maker.py").read_text(encoding="utf-8")

        self.assertIn("AI_LECTURER_WAV2LIP_BATCH_SIZE", source)
        self.assertIn("AI_LECTURER_WAV2LIP_RESIZE_FACTOR", source)
        self.assertIn('"--resize_factor"', source)
        self.assertNotIn('"--wav2lip_batch_size", "128"', source)

    def test_online_course_creation_has_markdown_fallback(self):
        source = (ROOT / "unified_gateway.py").read_text(encoding="utf-8")

        self.assertIn("def build_fallback_outline", source)
        self.assertIn("build_fallback_outline(request.raw_document", source)
        self.assertNotIn('raise HTTPException(status_code=500, detail="ç‘™ï½†ç€½ç’‡å‰§â–¼æ¾¶è¾«è§¦")', source)

    def test_wav2lip_cache_is_scoped_to_frame_geometry(self):
        source = (ROOT / "Wav2Lip_Offline" / "inference.py").read_text(encoding="utf-8")

        self.assertIn("def get_coords_cache_path", source)
        self.assertIn("resize_factor", source)
        self.assertIn("def coords_are_valid_for_frames", source)
        self.assertIn("not coords_are_valid_for_frames", source)
        self.assertNotIn('cache_path = args.face + ".coords.npy"', source)

    def test_offline_gateway_can_be_disabled_before_background_task_starts(self):
        source = (ROOT / "unified_gateway.py").read_text(encoding="utf-8")

        self.assertIn("AI_LECTURER_OFFLINE_ENABLED", source)
        self.assertIn("def is_offline_video_enabled", source)
        self.assertIn("if not is_offline_video_enabled()", source)
        self.assertIn("status_code=503", source)
        self.assertIn("bg_tasks.add_task", source)


if __name__ == "__main__":
    unittest.main()
