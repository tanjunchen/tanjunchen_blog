#!/usr/bin/env bash
# Render the DeepInfer article SVGs to 2x PNGs with headless Chrome.
set -euo pipefail

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DIR="$(cd "$(dirname "$0")/.." && pwd)/static/images/2026-11-14-deepinfer-inference-system"
PROFILE="/tmp/chrome-dsh-deepinfer"
mkdir -p "$PROFILE"

for svg in "$DIR"/*.svg; do
  base="${svg%.svg}"
  w=$(grep -o 'width="[0-9]*"' "$svg" | head -1 | grep -o '[0-9]*')
  h=$(grep -o 'height="[0-9]*"' "$svg" | head -1 | grep -o '[0-9]*')
  html="/tmp/deepinfer_render.html"
  svg_url="file://$(cd "$(dirname "$svg")" && pwd)/$(basename "$svg")"
  {
    echo '<html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:#fff}svg{display:block}</style></head><body>'
    cat "$svg"
    echo '</body></html>'
  } > "$html"
  "$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
    --user-data-dir="$PROFILE" --force-device-scale-factor=2 \
    --window-size="$w,$h" --screenshot="${base}.png" "file://$html" >/dev/null 2>&1
  echo "rendered $(basename "$base").png (${w}x${h} -> 2x)"
done

# Remove the bottom 12 CSS px artifact from headless-Chrome screenshots.
DIR="$DIR" python3 - <<'PYEOF'
from PIL import Image, ImageDraw
import glob, os
root = os.environ["DIR"]
for path in glob.glob(os.path.join(root, "*.png")):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    ImageDraw.Draw(im).rectangle([0, h - 24, w, h], fill="white")
    # Flat-color diagrams quantize cleanly; 256-color PNG keeps text crisp
    # while cutting file size by roughly 60%.
    im = im.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                     dither=Image.Dither.NONE)
    im.save(path, optimize=True)
PYEOF
