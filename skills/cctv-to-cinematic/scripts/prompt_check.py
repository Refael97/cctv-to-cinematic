#!/usr/bin/env python3
"""Pre-generation prompt review: lint the master prompt and build one source sheet per shot.

  python3 prompt_check.py prompt.txt ref.mp4 --out review/ [--min-chars 12000 --max-chars 21000]

ref.mp4 is the reference window (AI 00:00.0 = its first frame). Exit code 1 if any ERROR.
"""
import argparse, os, re, subprocess
from PIL import Image, ImageDraw
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from contact_sheet import extract, label, font

SECTIONS = ["SCENE CONTEXT", "REFERENCE CONTROL", "SPEED AND SYNC", "CAMERA VARIETY",
            "WORLD MAP", "CAST & CONTINUITY", "SHOT LIST", "EDITING RHYTHM", "LOOK"]
SHOT_RE = re.compile(r"^S(\d+)\s*[—–-]+\s*(\d+):(\d+(?:\.\d+)?)\s*[–-]\s*(\d+):(\d+(?:\.\d+)?)\s*[—–-]+\s*(.*)$")


def secs(m, s):
    return int(m) * 60 + float(s)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def parse_shots(lines):
    shots = []
    for i, ln in enumerate(lines):
        m = SHOT_RE.match(ln.strip())
        if m:
            shots.append({"n": int(m.group(1)), "start": secs(m.group(2), m.group(3)),
                          "end": secs(m.group(4), m.group(5)), "title": m.group(6).strip(), "line": i, "body": []})
    for k, s in enumerate(shots):
        stop = shots[k + 1]["line"] if k + 1 < len(shots) else len(lines)
        body = []
        for ln in lines[s["line"] + 1:stop]:
            if ln.strip() and ln.strip().isupper() and not ln.startswith(" "):
                break  # next section header
            body.append(ln)
        s["body"] = body
    return shots


def lint(text, shots, dur, a):
    issues = []
    err = lambda m: issues.append(("ERROR", m))
    warn = lambda m: issues.append(("WARN", m))

    n = len(text)
    if n < a.min_chars or n > a.max_chars:
        warn(f"length {n} chars, outside {a.min_chars}-{a.max_chars}")
    for sec in SECTIONS:
        if not re.search(rf"^{re.escape(sec)}\b", text, re.M):
            err(f"missing section: {sec}")
    if not shots:
        err("no shots parsed (expected lines like 'S1 — 00:00.0–00:02.0 — camera')")
        return issues

    # coverage
    t = 0.0
    for s in shots:
        if abs(s["start"] - t) > 0.01:
            err(f"S{s['n']}: starts at {s['start']:.2f}, previous shot ends at {t:.2f} ({'gap' if s['start'] > t else 'overlap'})")
        if s["end"] <= s["start"]:
            err(f"S{s['n']}: end {s['end']:.2f} <= start {s['start']:.2f}")
        t = s["end"]
    if abs(t - round(dur)) > 0.3 and abs(t - dur) > 0.3:
        err(f"shots end at {t:.2f}, reference window is {dur:.2f}s")
    if [s["n"] for s in shots] != list(range(1, len(shots) + 1)):
        warn("shot numbers are not 1..N in order")

    header = re.search(r"(\d+)\s+hard-cut shots", text)
    if header and int(header.group(1)) != len(shots):
        err(f"header says {header.group(1)} shots, SHOT LIST has {len(shots)}")

    # per-shot body
    for s in shots:
        body = "\n".join(s["body"])
        if "MUST NOT" not in body:
            warn(f"S{s['n']}: no MUST NOT line")
        if "End state" not in body and s is not shots[-1]:
            warn(f"S{s['n']}: no End state")
        side = re.sub(r"\b(left|right) (hand|arm|foot|leg|wrist|knee|side of (his|her|its) body)\b|\bright (at|next|there|away|after|before|in|on|up)\b", "", body, flags=re.I)
        if re.search(r"\b(left|right)\b", side, re.I):
            warn(f"S{s['n']}: uses left/right - prefer compass directions")
        for ts in re.findall(r"(\d+):(\d+\.\d+)", body):
            v = secs(*ts)
            if v < s["start"] - 0.01 or v > s["end"] + 0.01:
                err(f"S{s['n']}: timecode {ts[0]}:{ts[1]} is outside the shot ({s['start']:.2f}-{s['end']:.2f})")

    # speed consistency
    speed = re.search(r"^SPEED AND SYNC.*?(?=^\S[A-Z &]+$)", text, re.M | re.S)
    if speed and re.search(r"slow motion|slower than real time", speed.group(0), re.I):
        for bad in ["real-time speed", "real time speed", "no slow motion", "Real-time speed throughout"]:
            if bad.lower() in text.lower():
                err(f"SPEED AND SYNC says slow motion but prompt also says '{bad}'")
    if "Appearance gate" not in text and "appearance gate" not in text:
        warn("no appearance gate - add one for every character who enters mid-clip")
    if not re.search(r"security-camera footage|look like (the )?security", text, re.I):
        warn("no 'no shot may look like security-camera footage' rule")
    return issues


def shot_sheets(ref, shots, out, width=240, fps=4):
    os.makedirs(out, exist_ok=True)
    paths = []
    for s in shots:
        dur = max(s["end"] - s["start"], 0.25)
        frames = extract(ref, s["start"], dur + 0.01, fps, width)
        if not frames:
            continue
        w, h = frames[0][1].size
        cols = min(len(frames), 8)
        rows = -(-len(frames) // cols)
        head = 70
        sheet = Image.new("RGB", (w * cols, h * rows + head), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        d.text((10, 8), f"S{s['n']}  {s['start']:05.2f}-{s['end']:05.2f}", font=font(24), fill=(255, 220, 0))
        d.text((10, 40), s["title"][:150], font=font(16), fill=(230, 230, 230))
        for i, (t, im) in enumerate(frames):
            sheet.paste(label(im, f"{t:05.2f}", 16), ((i % cols) * w, head + (i // cols) * h))
        p = os.path.join(out, f"shot_S{s['n']:02d}.jpg")
        sheet.save(p, quality=88)
        paths.append(p)
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("ref")
    ap.add_argument("--out", default="review")
    ap.add_argument("--min-chars", type=int, default=12000)
    ap.add_argument("--max-chars", type=int, default=21000)
    ap.add_argument("--no-sheets", action="store_true")
    a = ap.parse_args()

    text = open(a.prompt, encoding="utf-8").read()
    lines = text.splitlines()
    shots = parse_shots(lines)
    dur = duration(a.ref)
    issues = lint(text, shots, dur, a)

    print(f"{len(text)} chars, {len(shots)} shots, reference {dur:.2f}s")
    for lvl, m in issues:
        print(f"{lvl}: {m}")
    if not issues:
        print("lint clean")
    if not a.no_sheets and shots:
        for p in shot_sheets(a.ref, shots, a.out):
            print("sheet:", p)
    raise SystemExit(1 if any(l == "ERROR" for l, _ in issues) else 0)


if __name__ == "__main__":
    main()
