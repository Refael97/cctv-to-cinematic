#!/usr/bin/env python3
"""Timestamped contact sheet without ffmpeg drawtext (PIL draws the labels).

  python3 contact_sheet.py in.mp4 --start 0 --dur 4 --fps 4 --out sheet_0.jpg [--crop W:H:X:Y] [--cols 4] [--width 480]
"""
import argparse, subprocess, tempfile, glob, os
from PIL import Image, ImageDraw, ImageFont


def font(size):
    for p in ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Helvetica.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def extract(src, start, dur, fps, width, crop=None):
    tmp = tempfile.mkdtemp()
    vf = (f"crop={crop}," if crop else "") + f"fps={fps},scale={width}:-2"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(dur), "-i", src,
                    "-vf", vf, os.path.join(tmp, "f_%04d.png")], check=True)
    files = sorted(glob.glob(os.path.join(tmp, "f_*.png")))
    return [(start + i / fps, Image.open(f).convert("RGB")) for i, f in enumerate(files)]


def label(img, text, size=22):
    d = ImageDraw.Draw(img)
    f = font(size)
    x0, y0, x1, y1 = d.textbbox((8, 8), text, font=f)
    d.rectangle((x0 - 4, y0 - 3, x1 + 4, y1 + 3), fill=(0, 0, 0))
    d.text((8, 8), text, font=f, fill=(255, 220, 0))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--dur", type=float, default=4)
    ap.add_argument("--fps", type=float, default=4)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--crop")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    frames = extract(a.src, a.start, a.dur, a.fps, a.width, a.crop)
    if not frames:
        raise SystemExit("no frames")
    w, h = frames[0][1].size
    rows = -(-len(frames) // a.cols)
    sheet = Image.new("RGB", (w * a.cols, h * rows))
    for i, (t, im) in enumerate(frames):
        sheet.paste(label(im, f"{t:05.2f}s"), ((i % a.cols) * w, (i // a.cols) * h))
    sheet.save(a.out, quality=90)
    print(a.out, len(frames), "frames")


if __name__ == "__main__":
    main()
