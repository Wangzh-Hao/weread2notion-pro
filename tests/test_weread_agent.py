import unittest

from weread2notionpro.weread_agent import (
    WeReadAgentClient,
    WeReadAgentError,
    WeReadSkillUpgradeRequired,
    normalize_read_times,
)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, bodies):
        self.bodies = iter(bodies)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(next(self.bodies))


class WeReadAgentClientTests(unittest.TestCase):
    def test_annual_daily_read_times_are_normalized(self):
        session = FakeSession([{"dailyReadTimes": {"1735660800": 125.9}}])
        client = WeReadAgentClient(api_key="wrk-test", session=session)

        result = client.get_daily_read_times(2025)

        self.assertEqual(result, {1735660800: 125})
        payload = session.calls[0][1]["json"]
        self.assertEqual(payload["api_name"], "/readdata/detail")
        self.assertEqual(payload["mode"], "annually")
        self.assertEqual(payload["skill_version"], "1.0.4")

    def test_upgrade_notice_stops_processing(self):
        session = FakeSession([{"upgrade_info": {"message": "请升级"}}])
        client = WeReadAgentClient(api_key="wrk-test", session=session)

        with self.assertRaisesRegex(WeReadSkillUpgradeRequired, "请升级"):
            client.get_read_data()

    def test_nested_api_error_is_reported(self):
        session = FakeSession([{"data": {"errcode": -1, "errmsg": "无权限"}}])
        client = WeReadAgentClient(api_key="wrk-test", session=session)

        with self.assertRaisesRegex(WeReadAgentError, "无权限"):
            client.get_read_data()

    def test_falls_back_to_monthly_daily_buckets(self):
        monthly = [
            {"readTimes": {str(1704067200 + month * 86400): month}}
            for month in range(1, 13)
        ]
        session = FakeSession([{}, *monthly])
        client = WeReadAgentClient(api_key="wrk-test", session=session)

        result = client.get_daily_read_times(2024)

        self.assertEqual(len(result), 12)
        self.assertEqual(len(session.calls), 13)
        self.assertTrue(
            all(call[1]["json"]["mode"] == "monthly" for call in session.calls[1:])
        )

    def test_millisecond_timestamps_are_supported(self):
        self.assertEqual(
            normalize_read_times({"1735660800000": "60"}),
            {1735660800: 60},
        )


if __name__ == "__main__":
    unittest.main()
