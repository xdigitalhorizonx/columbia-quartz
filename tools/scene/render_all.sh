#!/usr/bin/env bash
# Renders everything the homepage needs from scene.blend, then exports the WebP sets.
#   bash tools/scene/render_all.sh <src> [count]      (src defaults to C:/dev/columbia-quartz-source/3d)
# About an hour on an RTX 3070 Ti: four endpoint stills, 120 frames 1920x1080 and 120 frames 720x1280.
# Run one at a time: two Blender renders on one GPU each take twice as long.
set -euo pipefail
SRC=${1:-C:/dev/columbia-quartz-source/3d}
COUNT=${2:-120}
BLENDER=${BLENDER:-C:/dev/tools/blender-5.2.3-windows-x64/blender.exe}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$SRC/renders"
run() {   # stops the whole run if Blender dies before it reports RENDER_OK
  "$BLENDER" -b "$SRC/scene.blend" --python "$HERE/render_move.py" -- "$@" 2>&1 \
    | grep --line-buffered -E "FRAME_DONE|RENDER_OK|^NOTES|Traceback|Error:" | tee /dev/stderr | grep -q RENDER_OK
}
run --cam wide --res 3840x2160 --count 2 --frames 0,1 --samples 512 --out "$OUT/stills/wide" --notes "-0.8,-0.75,-0.7,-0.5,-0.45,-0.4"
run --cam tall --res 1440x2560 --count 2 --frames 0,1 --samples 512 --out "$OUT/stills/tall" --notes "-0.6,-0.55,-0.5,-0.45,-0.4,-0.35,-0.3"
run --cam wide --res 1920x1080 --count "$COUNT" --samples 256 --out "$OUT/wide"
run --cam tall --res 720x1280 --count "$COUNT" --samples 256 --out "$OUT/tall"
python "$HERE/export_frames.py" "$OUT" "$HERE/../../assets/scene"
echo ALL_DONE
