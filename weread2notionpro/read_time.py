"""Sync official WeRead daily reading data and the generated heatmap to Notion."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from weread2notionpro.notion_helper import NotionHelper
from weread2notionpro.utils import (
    format_date,
    get_date,
    get_icon,
    get_number,
    get_relation,
    get_title,
)
from weread2notionpro.weread_agent import WeReadAgentClient, normalize_read_times


TIME_ZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
HEATMAP_GUIDE = "https://mp.weixin.qq.com/s?__biz=MzI1OTcxOTI4NA==&mid=2247484145&idx=1&sn=81752852420b9153fc292b7873217651&chksm=ea75ebeadd0262fc65df100370d3f983ba2e52e2fcde2deb1ed49343fbb10645a77570656728&token=157143379&lang=zh_CN#rd"


def insert_to_notion(notion_helper, page_id, timestamp, duration):
    local_date = datetime.utcfromtimestamp(timestamp) + timedelta(hours=8)
    parent = {"database_id": notion_helper.day_database_id, "type": "database_id"}
    properties = {
        "标题": get_title(format_date(local_date, "%Y年%m月%d日")),
        "日期": get_date(start=format_date(local_date)),
        "时长": get_number(duration),
        "时间戳": get_number(timestamp),
        "年": get_relation([notion_helper.get_year_relation_id(local_date)]),
        "月": get_relation([notion_helper.get_month_relation_id(local_date)]),
        "周": get_relation([notion_helper.get_week_relation_id(local_date)]),
    }
    if page_id is not None:
        notion_helper.client.pages.update(page_id=page_id, properties=properties)
    else:
        notion_helper.client.pages.create(
            parent=parent,
            icon=get_icon("https://www.notion.so/icons/target_red.svg"),
            properties=properties,
        )


def get_heatmap_file():
    folder = Path("OUT_FOLDER")
    if not folder.is_dir():
        return None
    files = sorted(folder.glob("*.svg"))
    return files[0].name if files else None


def load_read_times(year):
    cache_file = os.getenv("WEREAD_READ_TIMES_FILE")
    if cache_file and Path(cache_file).is_file():
        cached = json.loads(Path(cache_file).read_text(encoding="utf-8"))
        if int(cached.get("year", 0)) == int(year):
            return normalize_read_times(cached.get("readTimes", {}))
    return WeReadAgentClient().get_daily_read_times(year)


def update_heatmap(notion_helper):
    image_file = get_heatmap_file()
    repository = os.getenv("REPOSITORY")
    ref = os.getenv("REF", "refs/heads/main").split("/")[-1]
    if image_file and repository:
        image_url = f"https://raw.githubusercontent.com/{repository}/{ref}/OUT_FOLDER/{image_file}"
        heatmap_url = f"https://heatmap.malinkang.com/?image={image_url}"
        if notion_helper.heatmap_block_id:
            notion_helper.update_heatmap(
                block_id=notion_helper.heatmap_block_id,
                url=heatmap_url,
            )
            return
    print(f"更新热力图失败，没有找到生成的 SVG 或热力图占位。具体参考：{HEATMAP_GUIDE}")


def sync_daily_read_times(notion_helper, read_times, selected_year):
    read_times = dict(sorted(read_times.items()))
    now = datetime.now(TIME_ZONE)
    if selected_year == now.year:
        today_timestamp = int(
            datetime(now.year, now.month, now.day, tzinfo=TIME_ZONE).timestamp()
        )
        read_times.setdefault(today_timestamp, 0)

    results = notion_helper.query_all(database_id=notion_helper.day_database_id)
    for result in results:
        properties = result.get("properties", {})
        timestamp = properties.get("时间戳", {}).get("number")
        duration = properties.get("时长", {}).get("number")
        if timestamp in read_times:
            value = read_times.pop(timestamp)
            if value != duration:
                insert_to_notion(
                    notion_helper,
                    page_id=result.get("id"),
                    timestamp=timestamp,
                    duration=value,
                )
    for timestamp, duration in read_times.items():
        insert_to_notion(
            notion_helper,
            page_id=None,
            timestamp=int(timestamp),
            duration=duration,
        )


def main():
    selected_year = int(os.getenv("YEAR") or datetime.now(TIME_ZONE).year)
    notion_helper = NotionHelper()
    update_heatmap(notion_helper)
    read_times = load_read_times(selected_year)
    sync_daily_read_times(notion_helper, read_times, selected_year)


if __name__ == "__main__":
    main()
