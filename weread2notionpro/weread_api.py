"""Compatibility adapter backed by the official WeRead Agent API."""

import hashlib
import re

from weread2notionpro.weread_agent import WeReadAgentClient, WeReadAgentError


class WeReadApi:
    """Expose the legacy sync methods using the official Agent Gateway."""

    def __init__(self, client=None):
        self.client = client or WeReadAgentClient()

    def get_bookshelf(self):
        return self.client.request("/shelf/sync")

    def get_notebooklist(self):
        """Return every notebook using the documented lastSort cursor."""
        notebooks = []
        last_sort = None
        seen_cursors = set()
        while True:
            params = {"count": 100}
            if last_sort is not None:
                params["lastSort"] = last_sort
            data = self.client.request("/user/notebooks", **params)
            books = data.get("books") or []
            notebooks.extend(books)
            if not data.get("hasMore"):
                break
            if not books:
                raise WeReadAgentError("微信读书笔记本分页响应缺少 books 数据。")
            next_cursor = books[-1].get("sort")
            if next_cursor is None or next_cursor in seen_cursors:
                raise WeReadAgentError("微信读书笔记本分页游标无效。")
            seen_cursors.add(next_cursor)
            last_sort = next_cursor
        notebooks.sort(key=lambda item: item.get("sort", 0))
        return notebooks

    def get_bookinfo(self, bookId):
        data = self.client.request("/book/info", bookId=bookId)
        data.setdefault("bookId", bookId)
        category = data.get("category")
        if category and not data.get("categories"):
            data["categories"] = [{"title": category}]
        return data

    def get_bookmark_list(self, bookId):
        data = self.client.request("/book/bookmarklist", bookId=bookId)
        return data.get("updated") or []

    def get_read_info(self, bookId):
        data = self.client.request("/book/getprogress", bookId=bookId)
        progress_data = data.get("book") or {}
        progress = int(progress_data.get("progress") or 0)
        reading_time = int(progress_data.get("recordReadingTime") or 0)
        update_time = progress_data.get("updateTime")
        finish_time = progress_data.get("finishTime")
        return {
            "markedStatus": 4 if progress == 100 else (2 if progress > 0 else 1),
            # Legacy Notion mapping expects basis points and divides by 100.
            "readingProgress": progress * 100,
            "readingTime": reading_time,
            "finishedDate": finish_time,
            "lastReadingDate": update_time,
            "readingBookDate": update_time,
        }

    def get_review_list(self, bookId):
        reviews = []
        synckey = 0
        seen_cursors = set()
        while True:
            data = self.client.request(
                "/review/list/mine",
                bookid=bookId,
                synckey=synckey,
                count=100,
            )
            for item in data.get("reviews") or []:
                review = item.get("review") if isinstance(item, dict) else None
                if not isinstance(review, dict):
                    continue
                if review.get("chapterUid") is None:
                    review = {"chapterUid": 1000000, **review}
                reviews.append(review)
            if not data.get("hasMore"):
                break
            next_cursor = data.get("synckey")
            if next_cursor in (None, synckey) or next_cursor in seen_cursors:
                raise WeReadAgentError("微信读书想法分页游标无效。")
            seen_cursors.add(next_cursor)
            synckey = next_cursor
        return reviews

    def get_chapter_info(self, bookId):
        data = self.client.request("/book/chapterinfo", bookId=bookId)
        chapters = {
            item["chapterUid"]: item
            for item in data.get("chapters") or []
            if item.get("chapterUid") is not None
        }
        chapters[1000000] = {
            "chapterUid": 1000000,
            "chapterIdx": 1000000,
            "updateTime": 0,
            "readAhead": 0,
            "title": "点评",
            "level": 1,
        }
        return chapters

    def transform_id(self, book_id):
        id_length = len(book_id)
        if re.match("^\\d*$", book_id):
            ary = []
            for i in range(0, id_length, 9):
                ary.append(format(int(book_id[i : min(i + 9, id_length)]), "x"))
            return "3", ary

        result = ""
        for character in book_id:
            result += format(ord(character), "x")
        return "4", [result]

    def calculate_book_str_id(self, book_id):
        digest = hashlib.md5(book_id.encode("utf-8")).hexdigest()
        result = digest[0:3]
        code, transformed_ids = self.transform_id(book_id)
        result += code + "2" + digest[-2:]

        for index, transformed_id in enumerate(transformed_ids):
            hex_length_str = format(len(transformed_id), "x").zfill(2)
            result += hex_length_str + transformed_id
            if index < len(transformed_ids) - 1:
                result += "g"

        if len(result) < 20:
            result += digest[0 : 20 - len(result)]

        result += hashlib.md5(result.encode("utf-8")).hexdigest()[0:3]
        return result

    def get_url(self, book_id):
        return f"https://weread.qq.com/web/reader/{self.calculate_book_str_id(book_id)}"
