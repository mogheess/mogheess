#!/usr/bin/env python3
"""Render the profile contribution chart from GitHub's GraphQL API."""

from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

USER = os.environ.get("GITHUB_USER", "mogheess")
OUT = Path(__file__).resolve().parents[1] / "profile-assets" / "activity.gif"
W, H, FRAMES = 960, 220, 48
BG = (5, 8, 6)
GRID = (25, 32, 23)
MUTED = (116, 125, 106)
ACID = (190, 255, 62)
PALE = (231, 255, 202)
FONT = ImageFont.load_default()

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}
"""


def contribution_data() -> tuple[list[int], int]:
    response = subprocess.check_output(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={USER}"],
        text=True,
    )
    payload = json.loads(response)
    calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [sum(day["contributionCount"] for day in week["contributionDays"]) for week in calendar["weeks"]]
    return weeks[-52:], calendar["totalContributions"]


def frame(values: list[int], total: int, frame_no: int) -> Image.Image:
    t = frame_no / FRAMES
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = 38, 44, W - 28, H - 34

    for y in range(top, bottom + 1, 30):
        draw.line((left, y, right, y), fill=GRID)
    for x in range(left, right + 1, 112):
        draw.line((x, top, x, bottom), fill=(13, 18, 12))

    max_value = max(max(values), 1)
    points = []
    for index, value in enumerate(values):
        x = left + index * (right - left) / (len(values) - 1)
        normalized = math.sqrt(value / max_value)
        y = bottom - 8 - normalized * (bottom - top - 18)
        points.append((x, y))

    # Dithered area below the real contribution curve.
    mask = Image.new("1", (W, H), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.polygon(points + [(right, bottom), (left, bottom)], fill=1)
    pixels = mask.load()
    for y in range(top, bottom):
        for x in range(left, right, 4):
            if pixels[x, y] and ((x // 4 + y // 4) % 4 < 2):
                shade = ACID if y < (top + bottom) // 2 else (104, 146, 41)
                draw.rectangle((x, y, x + 2, y + 2), fill=shade)

    # Glow and crisp line.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.line(points, fill=(*ACID, 120), width=6)
    glow = glow.filter(ImageFilter.GaussianBlur(7))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.line(points, fill=PALE, width=2)

    # Traveling shine follows the actual chart.
    cursor = t * (len(points) - 1)
    cursor_index = min(int(cursor), len(points) - 2)
    fraction = cursor - cursor_index
    x1, y1 = points[cursor_index]
    x2, y2 = points[cursor_index + 1]
    cx, cy = x1 + (x2 - x1) * fraction, y1 + (y2 - y1) * fraction
    draw.line((cx, top, cx, bottom), fill=(70, 88, 55), width=1)
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=(190, 255, 62), outline=PALE, width=2)

    # Small twinkling highlights on the three busiest weeks.
    peaks = sorted(range(len(values)), key=values.__getitem__, reverse=True)[:3]
    for offset, index in enumerate(peaks):
        if math.sin((t * math.tau * 2) + offset * 1.8) > 0.2:
            px, py = points[index]
            radius = 3 + offset
            draw.line((px - radius, py, px + radius, py), fill=PALE)
            draw.line((px, py - radius, px, py + radius), fill=PALE)

    draw.text((left, 17), "CONTRIBUTION ACTIVITY", font=FONT, fill=PALE)
    draw.text((left + 145, 17), "/ LAST 52 WEEKS", font=FONT, fill=MUTED)
    summary = f"{total:,} CONTRIBUTIONS"
    draw.text((right - draw.textlength(summary, font=FONT), 17), summary, font=FONT, fill=ACID)
    draw.text((left, H - 21), "52 WEEKS AGO", font=FONT, fill=MUTED)
    draw.text((right - 18, H - 21), "NOW", font=FONT, fill=MUTED, anchor="ra")
    return image


def main() -> None:
    values, total = contribution_data()
    frames = [frame(values, total, index) for index in range(FRAMES)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=70,
        loop=0,
        optimize=False,
        disposal=1,
    )
    print(OUT)


if __name__ == "__main__":
    main()
