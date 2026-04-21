import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholar.main import PDFViewer


def _viewer():
    return PDFViewer.__new__(PDFViewer)


class SourceTitleTests(unittest.TestCase):
    def test_bad_import_title_detects_punctuation_placeholder(self):
        viewer = _viewer()

        self.assertTrue(viewer._looks_like_bad_import_title(")"))
        self.assertTrue(viewer._looks_like_bad_import_title("Top line of doc"))
        self.assertTrue(viewer._looks_like_bad_import_title("doi:10.1234/example"))
        self.assertFalse(viewer._looks_like_bad_import_title("Emotional Arousal and Memory Binding"))

    def test_fallback_title_removes_local_import_prefixes(self):
        viewer = _viewer()

        title = viewer._fallback_title_from_path(
            r"C:\Users\mwgil\Documents\Articles\ZZZ_READ_Xie, W. et al. (2023).pdf"
        )

        self.assertEqual(title, "Xie, W. et al. (2023)")

    def test_usable_source_title_prefers_manual_good_title_over_bad_pdf_metadata(self):
        viewer = _viewer()

        title = viewer._usable_source_title(
            ")",
            r"C:\Users\mwgil\Documents\Articles\ZZZ_Kensinger (2004).pdf",
            "Emotional Arousal and Memory Binding",
        )

        self.assertEqual(title, "Emotional Arousal and Memory Binding")

    def test_usable_source_title_falls_back_to_filename_when_no_manual_title_exists(self):
        viewer = _viewer()

        title = viewer._usable_source_title(
            ")",
            r"C:\Users\mwgil\Documents\Articles\ZZZ_READ_Long et al. (2020).pdf",
            "",
        )

        self.assertEqual(title, "Long et al. (2020)")


if __name__ == "__main__":
    unittest.main()
