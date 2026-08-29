#!/usr/bin/env python3
"""Two BTS stills (pose A -> pose B) -> 5s 1080x1920 Short with optical-flow morph + handheld."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FFMPEG = "/usr/bin/ffmpeg"
FFPROBE = "/usr/bin/ffprobe"
OUT_W, OUT_H, FPS, NFRAMES = 1080, 1920, 24, 120
STILL = Path("/tmp/bts3/stills")
WORK = Path("/tmp/bts3/work")
OUT = Path("/workspace/bts_output")
ART = Path("/opt/cursor/artifacts")
QA = Path("/tmp/bts3/qa")

CROP = "crop=864:1536:80:0,scale=1080:1920:flags=lanczos,setsar=1"

PAIRS = [
    ("ahs_01a.png", "ahs_01b.png"),
    ("ahs_02a.png", "ahs_02b.png"),
    ("ahs_03a.png", "ahs_03b.png"),
    ("ahs_04a.png", "ahs_04b.png"),
    ("ahs_05a.png", "ahs_05b.png"),
    ("ahs_06a.png", "ahs_06b.png"),
    ("ahs_07a.png", "ahs_07b.png"),
    ("ahs_08a.png", "ahs_08b.png"),
    ("ahs_09a.png", "ahs_09b.png"),
    ("ahs_10a.png", "ahs_10b.png"),
]

HANDHELD = [
    "scale=1166:2074,crop=1080:1920:(in_w-1080)/2+11*sin(2*PI*t/1.28):(in_h-1920)/2+8*sin(2*PI*t/0.91)",
    "scale=1188:2112,crop=1080:1920:54+14*sin(2*PI*t/1.1)+6*sin(2*PI*t/0.45):96+10*sin(2*PI*t/0.86)",
    "scale=1210:2152,crop=1080:1920:(in_w-1080)/2+16*sin(2*PI*t/0.95)+7*sin(2*PI*t/0.4):(in_h-1920)/2+12*sin(2*PI*t/0.72)",
    "scale=1176:2092,crop=1080:1920:(in_w-1080)/2+18*t/5+8*sin(2*PI*t/1.4):(in_h-1920)/2+6*sin(2*PI*t/1.05)",
    "scale=1160:2062,crop=1080:1920:(in_w-1080)/2+10*sin(2*PI*t/1.55):(in_h-1920)/2+8*sin(2*PI*t/1.2)",
    "scale=1200:2134,crop=1080:1920:(in_w-1080)/2+15*sin(2*PI*t/0.88)+8*sin(2*PI*t/0.36):(in_h-1920)/2+11*sin(2*PI*t/0.7)",
    "scale=1180:2098,crop=1080:1920:(in_w-1080)/2+12*sin(2*PI*t/1.33):(in_h-1920)/2+9*sin(2*PI*t/1.0)",
    "scale=1154:2052,crop=1080:1920:(in_w-1080)/2+8*sin(2*PI*t/1.7):(in_h-1920)/2+7*sin(2*PI*t/1.35)",
    "scale=1196:2126,crop=1080:1920:(in_w-1080)/2+13*sin(2*PI*t/1.05):(in_h-1920)/2+10*sin(2*PI*t/0.8)",
    "scale=1172:2084,crop=1080:1920:(in_w-1080)/2+11*sin(2*PI*t/1.22):(in_h-1920)/2+8*sin(2*PI*t/0.97)",
]


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def prep_png(src: Path, dst: Path):
    WORK.mkdir(parents=True, exist_ok=True)
    run(
        [FFMPEG, "-y", "-i", str(src), "-vf", CROP, "-frames:v", "1", str(dst)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def encode_clip(i: int):
    n = f"{i:02d}"
    a_src = STILL / PAIRS[i - 1][0]
    b_src = STILL / PAIRS[i - 1][1]
    dst = OUT / f"VIDEO_{n}.mp4"
    OUT.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    # Pose A morphs into pose B over 5s (people actually change position)
    # plus handheld observer camera.
    fc = (
        f"[0:v]{CROP},fps={FPS},format=gbrp[a];"
        f"[1:v]{CROP},fps={FPS},format=gbrp[b];"
        f"[a][b]blend=all_expr='A*(1-T/5)+B*(T/5)',"
        f"{HANDHELD[i - 1]},"
        "eq=contrast=1.04:saturation=1.06:brightness='0.012*sin(2*PI*t/0.85)',"
        f"fps={FPS},format=yuv420p[v]"
    )
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-t", "5.2", "-i", str(a_src),
        "-loop", "1", "-t", "5.2", "-i", str(b_src),
        "-filter_complex", fc, "-map", "[v]",
        "-r", str(FPS), "-frames:v", str(NFRAMES), "-t", "5",
        "-c:v", "libx264", "-preset", "fast", "-crf", "17",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
        str(dst),
    ]
    print(f"morph {n}", file=sys.stderr)
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode()[-3500:])
        raise SystemExit(f"encode failed {n}")
    probe = subprocess.check_output(
        [
            FFPROBE, "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,nb_frames,duration",
            "-of", "csv=p=0", str(dst),
        ]
    ).decode().strip()
    print(f"VIDEO_{n} {probe} {dst.stat().st_size}", file=sys.stderr)
    qa = QA / f"v{n}.jpg"
    run(
        [FFMPEG, "-y", "-ss", "2.2", "-i", str(dst), "-frames:v", "1", "-q:v", "2", str(qa)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    ART.mkdir(parents=True, exist_ok=True)
    run(["cp", str(dst), str(ART / f"ahsoka_bts_{n}.mp4")])


def make_thumbnail():
    src = STILL / "ahs_01a.png"
    dst = OUT / "THUMBNAIL.png"
    vf = (
        "crop=792:1408:116:48,scale=1080:1920:flags=lanczos,setsar=1,"
        "eq=contrast=1.12:saturation=1.14:brightness=0.02,unsharp=5:5:0.75:5:5:0.0"
    )
    run(
        [FFMPEG, "-y", "-i", str(src), "-vf", vf, "-frames:v", "1", str(dst)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    run(["cp", str(dst), str(ART / "ahsoka_thumb_916.png")])
    print(f"THUMBNAIL {dst.stat().st_size}", file=sys.stderr)


def main():
    for i in range(1, 11):
        encode_clip(i)
    make_thumbnail()
    print("done")


if __name__ == "__main__":
    main()
