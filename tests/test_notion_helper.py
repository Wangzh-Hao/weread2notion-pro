import os
import unittest
from unittest.mock import patch

from weread2notionpro.notion_helper import NotionHelper


class FakePages:
    def __init__(self):
        self.updated = None
        self.created = None

    def update(self, **kwargs):
        self.updated = kwargs

    def create(self, **kwargs):
        self.created = kwargs


class FakeClient:
    def __init__(self):
        self.pages = FakePages()


class NotionHelperSecurityTests(unittest.TestCase):
    def make_helper(self, existing_pages):
        helper = NotionHelper.__new__(NotionHelper)
        helper.setting_database_id = "settings-database"
        helper.client = FakeClient()
        helper.query = lambda **kwargs: {"results": existing_pages}
        return helper

    @patch.dict(
        os.environ,
        {
            "NOTION_TOKEN": "ntn-sensitive",
            "NOTION_PAGE": "https://notion.example/page-id",
            "WEREAD_COOKIE": "cookie-sensitive",
        },
        clear=False,
    )
    def test_existing_plaintext_credentials_are_cleared(self):
        helper = self.make_helper(
            [
                {
                    "id": "settings-page",
                    "properties": {
                        "NotinToken": {"rich_text": []},
                        "WeReadCookie": {"rich_text": []},
                        "根据划线颜色设置文字颜色": {"checkbox": True},
                        "同步书签": {"checkbox": True},
                        "样式": {"select": {"name": "callout"}},
                    },
                }
            ]
        )

        helper.insert_to_setting_database()

        properties = helper.client.pages.updated["properties"]
        self.assertEqual(properties["NotinToken"], {"rich_text": []})
        self.assertEqual(properties["WeReadCookie"], {"rich_text": []})
        self.assertNotIn("ntn-sensitive", repr(properties))
        self.assertNotIn("cookie-sensitive", repr(properties))

    @patch.dict(
        os.environ,
        {
            "NOTION_TOKEN": "ntn-sensitive",
            "NOTION_PAGE": "https://notion.example/page-id",
            "WEREAD_COOKIE": "cookie-sensitive",
        },
        clear=False,
    )
    def test_new_settings_page_does_not_store_credentials(self):
        helper = self.make_helper([])

        helper.insert_to_setting_database()

        properties = helper.client.pages.created["properties"]
        self.assertNotIn("NotinToken", properties)
        self.assertNotIn("WeReadCookie", properties)
        self.assertNotIn("ntn-sensitive", repr(properties))
        self.assertNotIn("cookie-sensitive", repr(properties))


if __name__ == "__main__":
    unittest.main()
