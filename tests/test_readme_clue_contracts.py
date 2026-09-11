"""The reviewed opening keeps the puzzle answer implicit after normalization."""

from pathlib import Path
import unicodedata
import unittest


class ReadmeClueContracts(unittest.TestCase):
    def test_opening_is_new_editorial_clue_not_literal_answer(self):
        lines = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8").splitlines()
        opening = unicodedata.normalize("NFKC", lines[2]).lower()
        self.assertIn("apoploe’s red and yellow leaves", opening)
        self.assertIn("six letters unlock the lyric", opening)
        self.assertNotIn("melody", opening)
        self.assertTrue(lines[2].startswith("𓂀 "))


if __name__ == "__main__":
    unittest.main()
