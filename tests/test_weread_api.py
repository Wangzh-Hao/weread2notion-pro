import unittest

from weread2notionpro.weread_api import WeReadApi


class FakeResponse:
    def __init__(self, body, ok=True):
        self.body = body
        self.ok = ok
        self.text = repr(body)

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)

    def get(self, *args, **kwargs):
        return next(self.responses)


class WeReadApiTests(unittest.TestCase):
    def make_api(self, responses):
        api = WeReadApi.__new__(WeReadApi)
        api.session = FakeSession(responses)
        return api

    def test_successful_http_response_still_checks_cookie_error_code(self):
        api = self.make_api(
            [FakeResponse({}), FakeResponse({"errcode": -2012})]
        )

        with self.assertRaisesRegex(Exception, "Cookie 已过期"):
            api.get_bookshelf()

    def test_bookshelf_response_without_progress_is_returned(self):
        api = self.make_api([FakeResponse({}), FakeResponse({"books": []})])

        self.assertEqual(api.get_bookshelf(), {"books": []})


if __name__ == "__main__":
    unittest.main()
