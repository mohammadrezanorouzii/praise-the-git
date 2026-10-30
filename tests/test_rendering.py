import unittest
import base64
import io
import os
from unittest.mock import patch

from src.cli import get_coverage, hires_frame, split_cell, graphics_supported, graphics_image, kitty_frame


class RenderingTests(unittest.TestCase):
    def test_quadrants_preserve_two_color_patterns(self):
        black, gold = (0, 0, 0), (180, 120, 50)
        for expected_mask in range(16):
            pixels = [gold if expected_mask & (1 << i) else black for i in range(4)]
            mask, fg, bg = split_cell(pixels)
            reconstructed = [fg if mask & (1 << i) else bg for i in range(4)]
            self.assertEqual(reconstructed, pixels)

    def test_banner_fits_and_renders_at_various_sizes(self):
        for cols, rows in ((40, 15), (80, 24), (120, 30)):
            for message in ('CODE PUSHED', 'VICTORY ACHIEVED', 'HUMANITY RESTORED', 'YOU DIED', 'feature/bonfire'):
                with self.subTest(size=(cols, rows), message=message):
                    coverage = get_coverage(message, cols, rows)
                    self.assertLessEqual(len(coverage), (rows - 4) * 2)
                    self.assertLessEqual(len(coverage[0]), (cols - 4) * 2)
                    self.assertEqual(len(coverage) % 2, 0)
                    self.assertEqual(len(coverage[0]) % 2, 0)
                    self.assertGreater(max(map(max, coverage)), 0)
                    self.assertEqual(len(hires_frame(coverage, cols, 'gold', 1, None)), len(coverage) // 2)

    def test_graphics_detection_and_multiplexer_fallback(self):
        with patch.dict(os.environ, {"TERM": "xterm-kitty"}, clear=True):
            self.assertTrue(graphics_supported())
        with patch.dict(os.environ, {"TERM": "xterm-kitty", "TMUX": "yes"}, clear=True):
            self.assertFalse(graphics_supported())
        with patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=True):
            self.assertFalse(graphics_supported())

    def test_graphics_frame_is_chunked_decodable_png(self):
        from PIL import Image
        coverage = get_coverage("VICTORY ACHIEVED", 80, 24, scale=4)
        self.assertEqual(len(coverage) % 8, 0)
        self.assertEqual(len(coverage[0]) % 8, 0)
        self.assertLessEqual(len(coverage), 20 * 8)
        self.assertLessEqual(len(coverage[0]), 76 * 8)
        image = graphics_image(coverage, "gold")
        encoded = kitty_frame(image, 1.0, 42, len(coverage[0]) // 8, len(coverage) // 8)
        chunks = encoded.split("\x1b_G")[1:]
        self.assertGreater(len(chunks), 1)
        payloads = []
        for i, chunk in enumerate(chunks):
            self.assertTrue(chunk.endswith("\x1b\\"))
            control, payload = chunk[:-2].split(";", 1)
            self.assertIn("m=" + ("0" if i == len(chunks) - 1 else "1"), control)
            self.assertLessEqual(len(payload), 4096)
            payloads.append(payload)
        decoded = Image.open(io.BytesIO(base64.b64decode("".join(payloads))))
        self.assertEqual(decoded.size, image.size)
        self.assertEqual(decoded.getpixel((0, 0)), image.getpixel((0, 0)))

    def test_bitmap_fallback_fits_short_terminal(self):
        with patch("src.cli.rasterize", return_value=None):
            coverage = get_coverage("CODE PUSHED", 40, 8)
        self.assertLessEqual(len(coverage), 8)
        self.assertLessEqual(len(coverage[0]), 72)

    def test_whitespace_and_long_text_fit(self):
        for message in ('   ', 'A long message ' * 12):
            coverage = get_coverage(message, 40, 12)
            self.assertLessEqual(len(coverage), 16)
            self.assertLessEqual(len(coverage[0]), 72)


if __name__ == '__main__':
    unittest.main()
