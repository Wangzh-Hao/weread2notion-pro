import unittest
from unittest.mock import patch

from weread2notionpro import book


class FakeWeReadApi:
    def get_bookshelf(self):
        return {}

    def get_notebooklist(self):
        return []


class FakeNotionHelper:
    def get_all_book(self):
        return {}


class BookSyncTests(unittest.TestCase):
    @patch.object(book, "WeReadApi", return_value=FakeWeReadApi())
    @patch.object(book, "NotionHelper", return_value=FakeNotionHelper())
    def test_missing_optional_bookshelf_lists_are_treated_as_empty(
        self, notion_helper, weread_api
    ):
        book.main()

        self.assertEqual(book.archive_dict, {})
        self.assertEqual(book.notion_books, {})


if __name__ == "__main__":
    unittest.main()
