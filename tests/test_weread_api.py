import unittest

from weread2notionpro.weread_api import WeReadApi


class FakeAgentClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, api_name, **params):
        self.calls.append((api_name, params))
        return next(self.responses)


class WeReadApiTests(unittest.TestCase):
    def test_notebooks_follow_last_sort_pagination(self):
        client = FakeAgentClient(
            [
                {"books": [{"bookId": "a", "sort": 20}], "hasMore": 1},
                {"books": [{"bookId": "b", "sort": 10}], "hasMore": 0},
            ]
        )
        api = WeReadApi(client=client)

        result = api.get_notebooklist()

        self.assertEqual([item["bookId"] for item in result], ["b", "a"])
        self.assertEqual(client.calls[0], ("/user/notebooks", {"count": 100}))
        self.assertEqual(
            client.calls[1],
            ("/user/notebooks", {"count": 100, "lastSort": 20}),
        )

    def test_progress_is_mapped_to_legacy_notion_fields(self):
        client = FakeAgentClient(
            [
                {
                    "book": {
                        "progress": 45,
                        "recordReadingTime": 3600,
                        "updateTime": 1760000000,
                    }
                }
            ]
        )
        api = WeReadApi(client=client)

        result = api.get_read_info("book-1")

        self.assertEqual(result["readingProgress"], 4500)
        self.assertEqual(result["readingTime"], 3600)
        self.assertEqual(result["markedStatus"], 2)
        self.assertEqual(
            client.calls[0], ("/book/getprogress", {"bookId": "book-1"})
        )

    def test_reviews_follow_synckey_pagination(self):
        client = FakeAgentClient(
            [
                {
                    "reviews": [{"review": {"reviewId": "r1"}}],
                    "hasMore": 1,
                    "synckey": 12,
                },
                {
                    "reviews": [{"review": {"reviewId": "r2"}}],
                    "hasMore": 0,
                    "synckey": 13,
                },
            ]
        )
        api = WeReadApi(client=client)

        result = api.get_review_list("book-1")

        self.assertEqual([item["reviewId"] for item in result], ["r1", "r2"])
        self.assertEqual(result[0]["chapterUid"], 1000000)
        self.assertEqual(client.calls[1][1]["synckey"], 12)

    def test_chapter_info_adds_review_section(self):
        client = FakeAgentClient(
            [{"chapters": [{"chapterUid": 1, "title": "第一章"}]}]
        )
        api = WeReadApi(client=client)

        result = api.get_chapter_info("book-1")

        self.assertEqual(result[1]["title"], "第一章")
        self.assertEqual(result[1000000]["title"], "点评")


if __name__ == "__main__":
    unittest.main()
