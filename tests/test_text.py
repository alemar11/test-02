import unittest

from test_02 import count_words


class CountWordsTests(unittest.TestCase):
    def test_counts_words_separated_by_any_whitespace(self) -> None:
        self.assertEqual(count_words("  one two\tthree\nfour  "), 4)

    def test_empty_and_blank_strings_have_no_words(self) -> None:
        self.assertEqual(count_words(""), 0)
        self.assertEqual(count_words(" \t\n"), 0)


if __name__ == "__main__":
    unittest.main()
