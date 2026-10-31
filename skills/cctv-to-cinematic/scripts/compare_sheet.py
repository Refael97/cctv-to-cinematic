#!/usr/bin/env python3
"""Fidelity sheet: source frames on top, AI frames below, same timestamps.

  python3 compare_sheet.py source.mp4 ai.mp4 --start 0 --dur 4 --fps 4 --out cmp_0.jpg [--offset 0] [--src-crop W:H:X:Y]
"""
import argparse
from PIL import Image
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contact_sheet import extract, label


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("ai")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--dur", type=float, default=4)
    ap.add_argument("--fps", type=float, default=4)
    ap.add_argument("--offset", type=float, default=0, help="AI time = source time + offset")
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--src-crop")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    src = extract(a.src, a.start, a.dur, a.fps, a.width, a.src_crop)
    ai = extract(a.ai, a.start + a.offset, a.dur, a.fps, a.width)
    n = min(len(src), len(ai))
    w = a.width
    hs, ha = src[0][1].size[1], ai[0][1].size[1]
    sheet = Image.new("RGB", (w * n, hs + ha), (0, 0, 0))
    for i in range(n):
        sheet.paste(label(src[i][1], f"CCTV {src[i][0]:05.2f}", 16), (i * w, 0))
        sheet.paste(label(ai[i][1], f"AI {src[i][0]:05.2f}", 16), (i * w, hs))
    sheet.save(a.out, quality=90)
    print(a.out, n, "columns")


if __name__ == "__main__":
    main()
