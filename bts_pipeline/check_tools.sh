#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
ok=1
check() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "OK  $1  $($1 --version 2>&1 | head -1)"
  else
    echo "MISSING  $1"
    ok=0
  fi
}
check ffmpeg
check ffprobe
check yt-dlp
check deno
python3 -c "import curl_cffi; print('OK  curl_cffi', curl_cffi.__version__)"
test -x /workspace/bts_pipeline/from_youtube.py || chmod +x /workspace/bts_pipeline/from_youtube.py
echo "OK  from_youtube.py"
if [[ "$ok" -eq 1 ]]; then
  echo "READY: send a YouTube URL. Output will be 10x 5s 1080x1920 clips + 1 thumbnail."
  exit 0
fi
exit 1
