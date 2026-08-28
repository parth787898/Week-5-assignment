#!/usr/bin/env python3
"""Build 10 moving 5s 1080x1920 BTS clips from Avengers: Doomsday Special Look.

Scene layer = live 4K trailer (actors/VFX moving).
Gear layer = Mixkit camera-crew plates (operators, sliders, LCDs moving).
LCD overlay = the same live scene, so the monitor matches the take.
Observer handheld shake on the final composite.
Never pad; 9:16 crop only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

FFMPEG = "/usr/bin/ffmpeg"
FFPROBE = "/usr/bin/ffprobe"
OUT_W, OUT_H, FPS, NFRAMES = 1080, 1920, 24, 120
SRC = Path("/tmp/bts2/srcvid/special_look.webm")
RAW = Path("/tmp/bts/raw")
WORK = Path("/tmp/bts2/work")
OUT = Path("/workspace/bts_output")
ART = Path("/opt/cursor/artifacts")
QA = Path("/tmp/bts2/qa")


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def write_mask():
    """Bottom-weighted alpha: scene owns the top, camera owns the lower third."""
    h, w = OUT_H, OUT_W
    y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    a = np.zeros((h, w), dtype=np.float32)
    a += np.clip((y - 0.40) / 0.14, 0.0, 1.0) * 0.92
    path = WORK / "gear_mask.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            FFMPEG,
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-s",
            f"{w}x{h}",
            "-i",
            "pipe:0",
            "-frames:v",
            "1",
            str(path),
        ],
        input=(np.clip(a * 255, 0, 255).astype(np.uint8).tobytes()),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return path


def crop916_vf(w: int, h: int, xfrac: float) -> str:
    if w / h <= 9 / 16 + 0.02:
        crop_w = w - (w % 2)
        crop_h = int(crop_w * 16 / 9)
        crop_h -= crop_h % 2
        if crop_h > h:
            crop_h = h - (h % 2)
            crop_w = int(crop_h * 9 / 16)
            crop_w -= crop_w % 2
        x = max(0, int((w - crop_w) * xfrac))
        y = max(0, int((h - crop_h) * 0.30))
    else:
        crop_h = h - (h % 2)
        crop_w = int(crop_h * 9 / 16)
        crop_w -= crop_w % 2
        x = max(0, int((w - crop_w) * xfrac))
        y = 0
    x -= x % 2
    y -= y % 2
    return f"crop={crop_w}:{crop_h}:{x}:{y},scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1"


def probe_wh(path: Path):
    raw = subprocess.check_output(
        [
            FFPROBE,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(path),
        ]
    ).decode().strip()
    w, h = raw.split(",")[:2]
    return int(w), int(h)


def make_scene(dst: Path, start: float, xfrac: float, shake: str):
    w, h = probe_wh(SRC)
    crop = crop916_vf(w, h, xfrac)
    # scale slightly oversize then crop with handheld so the OBSERVER camera moves
    if shake == "push":
        motion = (
            "scale=w='1080*(1.02+0.08*t/5)':h='1920*(1.02+0.08*t/5)':eval=frame,"
            "crop=1080:1920:(in_w-1080)/2+8*sin(2*PI*t/1.6):(in_h-1920)/2+6*sin(2*PI*t/1.2)"
        )
    elif shake == "handheld":
        motion = (
            "scale=1128:2004,"
            "crop=1080:1920:24+16*sin(2*PI*t/1.15)+9*sin(2*PI*t/0.55):"
            "42+12*sin(2*PI*t/0.92)+7*sin(2*PI*t/0.48)"
        )
    elif shake == "pan_r":
        motion = (
            "scale=1188:2112,"
            "crop=1080:1920:min(in_w-1080\\,8+70*t/5)+6*sin(2*PI*t/1.7):"
            "(in_h-1920)/2+6*sin(2*PI*t/1.4)"
        )
    elif shake == "pan_l":
        motion = (
            "scale=1188:2112,"
            "crop=1080:1920:max(0\\,in_w-1080-8-70*t/5)+6*sin(2*PI*t/1.8):"
            "(in_h-1920)/2+6*sin(2*PI*t/1.3)"
        )
    else:
        motion = (
            "scale=1116:1984,"
            "crop=1080:1920:(in_w-1080)/2+10*sin(2*PI*t/2.4):(in_h-1920)/2+8*sin(2*PI*t/1.9)"
        )
    vf = f"{crop},fps={FPS},{motion},setsar=1,format=yuv420p"
    dst.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-i",
            str(SRC),
            "-t",
            "5.2",
            "-vf",
            vf,
            "-r",
            str(FPS),
            "-frames:v",
            str(NFRAMES),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            str(dst),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def make_gear(dst: Path, mix_id: str, mix_ss: float, xfrac: float, grade: str):
    src = RAW / f"{mix_id}.mp4"
    w, h = probe_wh(src)
    crop = crop916_vf(w, h, xfrac)
    if grade == "night":
        eq = "eq=brightness=-0.10:saturation=0.62:gamma=1.03,colorbalance=rs=0.12:gs=0.02:bs=-0.10"
    else:
        eq = "eq=brightness=-0.04:saturation=0.78,colorbalance=rs=0.04:bs=-0.04"
    vf = f"{crop},fps={FPS},{eq},setsar=1,format=yuv420p"
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            f"{mix_ss:.3f}",
            "-i",
            str(src),
            "-t",
            "5.2",
            "-vf",
            vf,
            "-r",
            str(FPS),
            "-frames:v",
            str(NFRAMES),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(dst),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


CLIPS = [
    # Doom throne — crane OTS
    dict(start=6.8, xfrac=0.50, mix="41289", mix_ss=3.0, mix_x=0.5, lcd=(500, 1220, 380, 250), shake="push", grade="night"),
    # Doom throne tighter — handheld
    dict(start=14.2, xfrac=0.50, mix="41269", mix_ss=1.5, mix_x=0.62, lcd=(520, 1180, 360, 240), shake="handheld", grade="night"),
    # Reed Richards profile
    dict(start=22.4, xfrac=0.55, mix="44076", mix_ss=1.0, mix_x=0.45, lcd=(430, 1280, 340, 220), shake="push", grade="night"),
    # Latverian mural
    dict(start=30.5, xfrac=0.48, mix="34486", mix_ss=2.0, mix_x=0.5, lcd=(430, 720, 300, 210), shake="pan_r", grade="day"),
    # Intense mustache CU
    dict(start=47.0, xfrac=0.50, mix="44056", mix_ss=2.5, mix_x=0.42, lcd=(360, 1080, 400, 280), shake="handheld", grade="night"),
    # Approach Shuri
    dict(start=58.5, xfrac=0.50, mix="44079", mix_ss=1.2, mix_x=0.55, lcd=(620, 1240, 300, 220), shake="pan_l", grade="night"),
    # Shuri / Black Panther
    dict(start=66.0, xfrac=0.48, mix="41289", mix_ss=10.0, mix_x=0.5, lcd=(500, 1220, 380, 250), shake="push", grade="night"),
    # Thor lightning
    dict(start=78.5, xfrac=0.22, mix="44066", mix_ss=1.0, mix_x=0.70, lcd=(400, 760, 420, 300), shake="handheld", grade="night"),
    # Doom + Sentinels
    dict(start=90.0, xfrac=0.50, mix="44076", mix_ss=5.5, mix_x=0.50, lcd=(430, 1280, 340, 220), shake="pan_r", grade="night"),
    # Video village / DIT on Doom
    dict(start=98.5, xfrac=0.50, mix="44071", mix_ss=4.0, mix_x=0.62, lcd=(820, 660, 240, 280), shake="drift", grade="night"),
]


def composite(i: int, spec: dict, mask: Path):
    n = f"{i:02d}"
    scene = WORK / f"scene_{n}.mp4"
    gear = WORK / f"gear_{n}.mp4"
    dst = OUT / f"VIDEO_{n}.mp4"
    qa = QA / f"v{n}.jpg"
    print(f"scene {n} @ {spec['start']}s", file=sys.stderr)
    make_scene(scene, spec["start"], spec["xfrac"], spec["shake"])
    print(f"gear  {n} mix {spec['mix']}", file=sys.stderr)
    make_gear(gear, spec["mix"], spec["mix_ss"], spec["mix_x"], spec["grade"])

    x, y, w, h = spec["lcd"]
    w -= w % 2
    h -= h % 2
    fc = (
        f"[0:v]fps={FPS},format=yuv420p[scene];"
        f"[1:v]fps={FPS},format=gbrap[gear_rgb];"
        f"[2:v]fps={FPS},scale={OUT_W}:{OUT_H},format=gray[mask];"
        f"[gear_rgb][mask]alphamerge[gear];"
        f"[scene][gear]overlay=0:0:format=auto[base];"
        f"[0:v]fps={FPS},scale={w}:{h}:flags=lanczos,setsar=1,"
        f"pad={w+16}:{h+16}:8:8:0x0d0d0d[lcd];"
        f"[base][lcd]overlay={x}:{y}:format=auto,"
        f"scale=1110:1974,crop=1080:1920:15+8*sin(2*PI*t/1.35):18+6*sin(2*PI*t/0.95),"
        f"setsar=1,fps={FPS},format=yuv420p[outv]"
    )
    cmd = [
        FFMPEG,
        "-y",
        "-i",
        str(scene),
        "-i",
        str(gear),
        "-loop",
        "1",
        "-framerate",
        str(FPS),
        "-t",
        "5",
        "-i",
        str(mask),
        "-filter_complex",
        fc,
        "-map",
        "[outv]",
        "-r",
        str(FPS),
        "-frames:v",
        str(NFRAMES),
        "-t",
        "5",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "17",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(dst),
    ]
    print(f"comp  {n}", file=sys.stderr)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode()[-3000:])
        raise SystemExit(f"composite failed {n}")
    QA.mkdir(parents=True, exist_ok=True)
    run(
        [
            FFMPEG,
            "-y",
            "-ss",
            "2.0",
            "-i",
            str(dst),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(qa),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    probe = subprocess.check_output(
        [
            FFPROBE,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames,duration",
            "-of",
            "csv=p=0",
            str(dst),
        ]
    ).decode().strip()
    print(f"VIDEO_{n} {probe}", file=sys.stderr)
    ART.mkdir(parents=True, exist_ok=True)
    run(["cp", str(dst), str(ART / f"doomsday_bts_{n}.mp4")])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    mask = write_mask()
    for i, spec in enumerate(CLIPS, 1):
        composite(i, spec, mask)
    print("done")


if __name__ == "__main__":
    main()
