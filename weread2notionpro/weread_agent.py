"""Client for the official WeRead Agent API Gateway."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests


GATEWAY_URL = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.4"
TIME_ZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


class WeReadAgentError(RuntimeError):
    """Raised when the official WeRead gateway cannot return usable data."""


class WeReadSkillUpgradeRequired(WeReadAgentError):
    """Raised when the gateway requires a newer skill version."""


class WeReadAgentClient:
    def __init__(self, api_key=None, session=None, timeout=30):
        self.api_key = api_key or os.getenv("WEREAD_API_KEY")
        if not self.api_key:
            raise WeReadAgentError(
                "缺少 WEREAD_API_KEY，请在 GitHub Actions Secrets 中配置微信读书 API Key。"
            )
        self.session = session or requests.Session()
        self.timeout = timeout

    def _request(self, api_name, **params):
        payload = {
            "api_name": api_name,
            "skill_version": SKILL_VERSION,
            **params,
        }
        try:
            response = self.session.post(
                GATEWAY_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise WeReadAgentError(f"微信读书官方接口请求失败：{exc}") from exc

        if not isinstance(body, dict):
            raise WeReadAgentError("微信读书官方接口返回了无法识别的数据格式。")

        upgrade_info = body.get("upgrade_info")
        if upgrade_info:
            message = (
                upgrade_info.get("message")
                if isinstance(upgrade_info, dict)
                else str(upgrade_info)
            )
            raise WeReadSkillUpgradeRequired(
                message or "微信读书 Skill 需要升级后才能继续。"
            )

        errcode = body.get("errcode", 0)
        if errcode not in (0, None):
            message = body.get("errmsg") or body.get("message") or "未知错误"
            raise WeReadAgentError(f"微信读书官方接口错误 {errcode}：{message}")

        for key in ("data", "result"):
            nested = body.get(key)
            if isinstance(nested, dict):
                nested_upgrade = nested.get("upgrade_info")
                if nested_upgrade:
                    message = (
                        nested_upgrade.get("message")
                        if isinstance(nested_upgrade, dict)
                        else str(nested_upgrade)
                    )
                    raise WeReadSkillUpgradeRequired(
                        message or "微信读书 Skill 需要升级后才能继续。"
                    )
                nested_errcode = nested.get("errcode", 0)
                if nested_errcode not in (0, None):
                    message = (
                        nested.get("errmsg")
                        or nested.get("message")
                        or "未知错误"
                    )
                    raise WeReadAgentError(
                        f"微信读书官方接口错误 {nested_errcode}：{message}"
                    )
                return nested
        return body

    def get_read_data(self, mode="monthly", base_time=0):
        return self._request(
            "/readdata/detail",
            mode=mode,
            baseTime=int(base_time),
        )

    def get_daily_read_times(self, year):
        """Return a {unix_timestamp: seconds} mapping for one calendar year."""
        year = int(year)
        base_time = int(datetime(year, 1, 1, tzinfo=TIME_ZONE).timestamp())
        annual = self.get_read_data(mode="annually", base_time=base_time)
        daily = annual.get("dailyReadTimes")
        if isinstance(daily, dict):
            return normalize_read_times(daily)

        today = datetime.now(TIME_ZONE).date()
        last_month = today.month if year == today.year else 12
        combined = {}
        for month in range(1, last_month + 1):
            month_time = int(datetime(year, month, 1, tzinfo=TIME_ZONE).timestamp())
            monthly = self.get_read_data(mode="monthly", base_time=month_time)
            buckets = monthly.get("readTimes")
            if not isinstance(buckets, dict):
                raise WeReadAgentError(
                    f"{year} 年 {month} 月响应中缺少每日 readTimes 数据。"
                )
            combined.update(normalize_read_times(buckets))
        return combined


def normalize_read_times(read_times):
    normalized = {}
    for raw_timestamp, raw_seconds in read_times.items():
        try:
            timestamp = int(raw_timestamp)
            if timestamp > 10_000_000_000:
                timestamp //= 1000
            seconds = max(0, int(raw_seconds))
        except (TypeError, ValueError) as exc:
            raise WeReadAgentError("阅读时长数据包含无效的时间戳或时长。") from exc
        normalized[timestamp] = seconds
    return normalized
