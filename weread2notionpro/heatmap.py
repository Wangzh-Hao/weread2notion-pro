"""Generate a GitHub-style SVG heatmap from official WeRead reading data."""

from __future__ import annotations

import json
import math
import os
import re
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from weread2notionpro.weread_agent import WeReadAgentClient


TIME_ZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _color(value, default):
    return value if value and HEX_COLOR.match(value) else default


def _mix(color, background, weight):
    left = tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
    right = tuple(int(background[index : index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(round(a * weight + b * (1 - weight)) for a, b in zip(left, right))
    return "#" + "".join(f"{channel:02X}" for channel in mixed)


def _thresholds(values):
    positive = sorted(value for value in values if value > 0)
    if not positive:
        return (0, 0, 0)

    def percentile(fraction):
        index = min(len(positive) - 1, max(0, math.ceil(len(positive) * fraction) - 1))
        return positive[index]

    return percentile(0.25), percentile(0.5), percentile(0.75)


def _level(seconds, thresholds):
    if seconds <= 0:
        return 0
    return 1 + sum(seconds > threshold for threshold in thresholds)


def _date_values(read_times, year):
    result = {}
    for timestamp, seconds in read_times.items():
        day = datetime.fromtimestamp(int(timestamp), TIME_ZONE).date()
        if day.year == year:
            result[day] = int(seconds)
    return result


def generate_heatmap(read_times, year, output_path, name=""):
    year = int(year)
    values = _date_values(read_times, year)
    thresholds = _thresholds(values.values())

    background = _color(os.getenv("HEATMAP_BACKGROUND_COLOR"), "#FFFFFF")
    track = _color(os.getenv("HEATMAP_TRACK_COLOR"), "#ACE7AE")
    special1 = _color(os.getenv("HEATMAP_SPECIAL_COLOR1"), "#69C16E")
    special2 = _color(os.getenv("HEATMAP_SPECIAL_COLOR2"), "#549F57")
    empty = _color(os.getenv("HEATMAP_EMPTY_COLOR"), "#EBEDF0")
    text = _color(os.getenv("HEATMAP_TEXT_COLOR"), "#24292F")
    colors = (empty, _mix(track, background, 0.55), track, special1, special2)

    cell = 11
    gap = 3
    step = cell + gap
    left = 48
    top = 54
    grid_start = date(year, 1, 1)
    grid_start -= timedelta(days=(grid_start.weekday() + 1) % 7)
    grid_end = date(year, 12, 31)
    weeks = ((grid_end - grid_start).days // 7) + 1
    width = left + weeks * step + 28
    height = top + 7 * step + 34
    total_seconds = sum(values.values())
    total_hours = total_seconds / 3600
    title = f"{name + ' ' if name else ''}{year} 微信读书"

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="{escape(title)}阅读热力图">'
        ),
        f'<rect width="100%" height="100%" rx="8" fill="{background}"/>',
        '<g font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Microsoft YaHei,sans-serif">',
        f'<text x="{left}" y="24" font-size="15" font-weight="600" fill="{text}">{escape(title)}</text>',
        f'<text x="{width - 28}" y="24" text-anchor="end" font-size="12" fill="{text}">共 {total_hours:.1f} 小时</text>',
    ]

    for row, label in ((1, "一"), (3, "三"), (5, "五")):
        y = top + row * step + cell - 2
        lines.append(f'<text x="{left - 12}" y="{y}" text-anchor="end" font-size="10" fill="{text}">{label}</text>')

    last_month = None
    current = grid_start
    while current <= grid_end:
        week = (current - grid_start).days // 7
        row = (current.weekday() + 1) % 7
        x = left + week * step
        y = top + row * step
        if current.year == year:
            if current.month != last_month and current.day <= 7:
                lines.append(
                    f'<text x="{x}" y="{top - 10}" font-size="10" fill="{text}">{current.month}月</text>'
                )
                last_month = current.month
            seconds = values.get(current, 0)
            fill = colors[_level(seconds, thresholds)]
            minutes = round(seconds / 60)
            lines.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{fill}">'
                f'<title>{current.isoformat()}：{minutes} 分钟</title></rect>'
            )
        current += timedelta(days=1)

    legend_x = width - 28 - (5 * step + 24)
    legend_y = height - 18
    lines.append(f'<text x="{legend_x}" y="{legend_y + 9}" font-size="10" fill="{text}">少</text>')
    for index, color in enumerate(colors):
        x = legend_x + 16 + index * step
        lines.append(f'<rect x="{x}" y="{legend_y}" width="{cell}" height="{cell}" rx="2" fill="{color}"/>')
    lines.append(f'<text x="{legend_x + 16 + 5 * step}" y="{legend_y + 9}" font-size="10" fill="{text}">多</text>')
    lines.extend(("</g>", "</svg>"))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main():
    now = datetime.now(TIME_ZONE)
    year = int(os.getenv("YEAR") or now.year)
    name = os.getenv("HEATMAP_NAME", "")
    read_times = WeReadAgentClient().get_daily_read_times(year)
    output = generate_heatmap(read_times, year, "OUT_FOLDER/weread.svg", name=name)

    cache_file = os.getenv("WEREAD_READ_TIMES_FILE")
    if cache_file:
        Path(cache_file).write_text(
            json.dumps(
                {
                    "year": year,
                    "readTimes": {str(key): value for key, value in read_times.items()},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    print(f"Generated {output} with {len(read_times)} daily records.")


if __name__ == "__main__":
    main()
