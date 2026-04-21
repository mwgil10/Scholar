import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholar.main import PDFViewer


def _viewer():
    viewer = PDFViewer.__new__(PDFViewer)
    viewer.current_char_index = []
    viewer.selection_regions = []
    viewer.selection_start_index = None
    viewer.selection_end_index = None
    return viewer


def _char(index, text, x0, y0, x1, y1, block=0, line=0):
    return {
        "index": index,
        "ch": text,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        "cx": (x0 + x1) / 2,
        "cy": (y0 + y1) / 2,
        "block": block,
        "line": line,
        "block_bx0": 0,
        "block_bx1": 200,
    }


class AnnotationGeometryTests(unittest.TestCase):
    def test_discontinuous_ctrl_selection_gets_visible_gap_marker(self):
        viewer = _viewer()
        text = "Alpha Beta Gamma"
        viewer.current_char_index = [
            _char(index, ch, index * 5, 10, index * 5 + 4, 20)
            for index, ch in enumerate(text)
        ]
        viewer.selection_regions = [(0, 4), (11, 15)]

        groups = viewer._selected_char_groups()
        rendered = viewer._selection_text_from_groups(groups)

        self.assertEqual(rendered, "Alpha [...] Gamma")

    def test_contiguous_selection_does_not_get_gap_marker(self):
        viewer = _viewer()
        text = "Alpha Beta"
        viewer.current_char_index = [
            _char(index, ch, index * 5, 10, index * 5 + 4, 20)
            for index, ch in enumerate(text)
        ]
        viewer.selection_regions = [(0, 4), (5, 9)]

        groups = viewer._selected_char_groups()
        rendered = viewer._selection_text_from_groups(groups)

        self.assertEqual(rendered, "Alpha Beta")

    def test_line_relative_rects_split_multiline_selection(self):
        viewer = _viewer()
        page_rect = SimpleNamespace(width=200, height=200)
        chars = [
            _char(0, "A", 10, 20, 20, 30, block=0, line=0),
            _char(1, "B", 20, 20, 30, 30, block=0, line=0),
            _char(2, "C", 10, 40, 20, 50, block=0, line=1),
            _char(3, "D", 20, 40, 30, 50, block=0, line=1),
        ]

        rects = viewer._chars_to_line_relative_rects(chars, page_rect)

        self.assertEqual(len(rects), 2)
        self.assertAlmostEqual(rects[0]["x"], 0.05)
        self.assertAlmostEqual(rects[0]["y"], 0.10)
        self.assertAlmostEqual(rects[0]["width"], 0.10)
        self.assertAlmostEqual(rects[1]["x"], 0.05)
        self.assertAlmostEqual(rects[1]["y"], 0.20)
        self.assertAlmostEqual(rects[1]["width"], 0.10)

    def test_valid_relative_rect_rejects_oversized_merged_box(self):
        viewer = _viewer()

        self.assertFalse(
            viewer._valid_relative_rect(
                {"x": 0.0, "y": 0.0, "width": 0.9, "height": 0.9},
                max_area=0.08,
            )
        )
        self.assertTrue(
            viewer._valid_relative_rect(
                {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.05},
                max_area=0.08,
            )
        )


if __name__ == "__main__":
    unittest.main()
