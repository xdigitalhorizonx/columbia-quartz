#!/usr/bin/env bash
# Renders everything the homepage needs from scene.blend, then exports the WebP sets.
#   bash tools/scene/render_all.sh <src> [count]      (src defaults to C:/dev/columbia-quartz-source/3d)
# About 75 minutes on an RTX 3070 Ti: 120 frames 1920x1080 + 120 frames 720x1280 + four endpoint stills.
set -euo pipefail
SRC=${1:-C:/dev/columbia-quartz-source/3d}
COUNT=${2:-120}
BLENDER=${BLENDER:-C:/dev/tools/blender-5.2.3-windows-x64/blender.exe}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$SRC/renders"
run() { "$BLENDER" -b "$SRC/scene.blend" --python "$HERE/render_move.py" -- "$@" 2>&1 | grep -E "FRAME_DONE|RENDER_OK|NOTES|Error|Traceback" || true; }
run --cam wide --res 3840x2160 --count 2 --frames 0,1 --samples 512 --out "$OUT/stills/wide" --notes "-0.8,-0.7,-0.6,-0.5,-0.45,-0.4,-0.35,-0.3"
run --cam tall --res 1440x2560 --count 2 --frames 0,1 --samples 512 --out "$OUT/stills/tall" --notes "-0.6,-0.55,-0.5,-0.45,-0.4,-0.35"
run --cam tall --res 720x1280 --count "$COUNT" --samples 384 --out "$OUT/tall"
run --cam wide --res 1920x1080 --count "$COUNT" --samples 384 --out "$OUT/wide"
python "$HERE/export_frames.py" "$OUT" "$HERE/../../assets/scene"
echo ALL_DONE
