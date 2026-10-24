#!/usr/bin/env python3
"""Read Tekken 8's on-screen input history (practice mode) from a 1080p 60 fps video.

Each history row = direction arrow, button dots, frames held. New rows appear at the top
and push the list down in one frame. A new top row is accepted when the old top row now
shows one place lower (a single bad read is ignored), or when it stays for 3 frames.
The video must be 60 fps: the number of video frames a row stays on top is its frame
count. Output: JSON list of rows in time order.

    python3 -I scripts/read_input_history.py VIDEO OUT.json [--start SEC] [--end SEC]

Layout values are for the input history at the left edge of a 1920x1080 frame
(Tekken 8, default HUD). Check them with --debug on a new video.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROW0_TOP, ROW_H = 229, 34
ROWS = 6                        # rows read on every frame (0 = top)
X0, CROP_W = 120, 120           # horizontal crop of the history column
ARROW_X = (124, 164)            # area searched for the arrow (it moves left when a button is shown)
RESYNC = 3                      # frames a new top row must stay before it is accepted unconfirmed
# Button dot centres (x, y offset from the row top). Tekken's 2x2 button icon:
# 1 upper-left, 2 upper-right, 3 lower-left, 4 lower-right.
DOTS = {1: (169.5, 16), 2: (179.5, 10.5), 3: (173.8, 26.8), 4: (184.5, 21)}

_TPL = np.load(Path(__file__).with_name("arrow_templates.npz"))
_K = np.ones((3, 3), np.uint8)
TPL = [cv2.GaussianBlur(cv2.dilate(m.astype(np.uint8) * 255, _K), (3, 3), 0).astype(np.float32)
       for m in _TPL["masks"]]
TPL_LABELS = [str(x) for x in _TPL["labels"]]


def row_of(gray, k):
    top = ROW0_TOP + k * ROW_H
    return gray[top:top + ROW_H]


def read_arrow(row):
    """Direction in a row: best match against clean arrow templates."""
    area = row[1:33, ARROW_X[0]:ARROW_X[1]]
    mask = (area > 215).astype(np.uint8) * 255
    if int((mask > 0).sum()) < 25:
        return "n"
    m = cv2.GaussianBlur(cv2.dilate(mask, _K), (3, 3), 0).astype(np.float32)
    scores = [float(cv2.matchTemplate(m, t, cv2.TM_CCOEFF_NORMED).max()) for t in TPL]
    best = int(np.argmax(scores))
    return TPL_LABELS[best] if scores[best] >= 0.45 else "?"


def read_buttons(row):
    vals = {b: float(row[int(y) - 2:int(y) + 3, int(x) - 2:int(x) + 3].mean()) for b, (x, y) in DOTS.items()}
    hi = max(vals.values())
    if hi < 190:
        return ()
    return tuple(sorted(b for b, v in vals.items() if v > 190 and v > hi - 40))


def frames(video, start, end):
    h = ROWS * ROW_H
    cmd = [shutil.which("ffmpeg") or "ffmpeg", "-v", "error"]
    if start:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(video)]
    if end:
        cmd += ["-t", str(end - (start or 0))]
    cmd += ["-vf", f"crop={CROP_W}:{h}:{X0}:{ROW0_TOP},format=gray", "-f", "rawvideo", "-"]
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        i = 0
        while True:
            buf = p.stdout.read(CROP_W * h)
            if len(buf) < CROP_W * h:
                break
            crop = np.frombuffer(buf, np.uint8).reshape(h, CROP_W)
            g = np.zeros((ROW0_TOP + h, X0 + CROP_W), np.uint8)   # back to frame coordinates
            g[ROW0_TOP:, X0:] = crop
            yield i, g
            i += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--end", type=float, default=0)
    ap.add_argument("--debug", action="store_true", help="print the rows read on every frame")
    a = ap.parse_args()
    if not a.video.is_file():
        sys.exit("video not found")

    fps = 60.0
    rows, top, pending = [], None, None
    for i, g in frames(a.video.resolve(), a.start, a.end):
        s0 = (read_arrow(row_of(g, 0)), read_buttons(row_of(g, 0)))
        s1 = (read_arrow(row_of(g, 1)), read_buttons(row_of(g, 1)))
        if a.debug:
            print(round(a.start + i / fps, 3), s0, s1)
        if top is None:
            top = {"s": s0, "f": i}
            continue
        if s0 == top["s"]:
            pending = None
            continue
        if pending is None or pending["s"] != s0:
            pending = {"s": s0, "f": i}
        confirmed = s1 == top["s"]
        if not confirmed and i - pending["f"] < RESYNC:
            continue
        rows.append({"t": round(a.start + top["f"] / fps, 3), "dir": top["s"][0], "btn": list(top["s"][1]),
                     "n": pending["f"] - top["f"], "sure": confirmed})
        top, pending = {"s": s0, "f": pending["f"]}, None
    a.out.write_text(json.dumps(rows, separators=(",", ":")))
    print(f"{len(rows)} rows")


if __name__ == "__main__":
    main()
