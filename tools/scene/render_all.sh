#!/usr/bin/env bash
# Renders everything the homepage needs from scene.blend, then exports the WebP sets.
#   bash tools/scene/render_all.sh [src]      (src defaults to C:/dev/columbia-quartz-source/3d)
# About two hours on an RTX 3070 Ti: the four hold stills (plan, island edge, sink, kitchen) at 4K for both
# framings, then the 288-frame move at 1920x1080 and 720x1280. NOTES lines (for home.js) go to render.log.
# Run one at a time: two Blender renders on one GPU each take twice as long.
set -euo pipefail
SRC=${1:-C:/dev/columbia-quartz-source/3d}
BLENDER=${BLENDER:-C:/dev/tools/blender-5.2.3-windows-x64/blender.exe}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$SRC/renders"
LOG="$OUT/render.log"
mkdir -p "$OUT"; : > "$LOG"
run() {   # stops the whole run if Blender dies before it reports RENDER_OK
  "$BLENDER" -b "$SRC/scene.blend" --python "$HERE/render_move.py" -- "$@" 2>&1 \
    | grep --line-buffered -E "FRAME_DONE|RENDER_OK|^NOTES|Traceback|Error:" | tee -a "$LOG" | grep -q RENDER_OK
}
EDGE="-0.8,-0.75,-0.7,-0.6,-0.5,-0.45,-0.4,-0.35,-0.3"
run --cam wide --res 3840x2160 --frames 0,119,191,287 --samples 512 --out "$OUT/stills/wide" --notes "$EDGE"
run --cam tall --res 1440x2560 --frames 0,119,191,287 --samples 512 --out "$OUT/stills/tall" --notes "$EDGE"
run --cam wide --res 1920x1080 --frames 0-287 --samples 256 --out "$OUT/wide"
run --cam tall --res 720x1280 --frames 0-287 --samples 256 --out "$OUT/tall"
python "$HERE/export_frames.py" "$OUT" "$HERE/../../assets/scene"
echo ALL_DONE | tee -a "$LOG"
