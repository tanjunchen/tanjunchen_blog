#!/usr/bin/env bash
# Render the KV panorama SVGs to 2x PNGs with headless Chrome.
set -euo pipefail

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DIR="$(cd "$(dirname "$0")/.." && pwd)/static/images/2026-11-21-kv-cache-panorama"
PROFILE="/tmp/chrome-dsh-kv-panorama"
mkdir -p "$PROFILE"

for svg in "$DIR"/*.svg; do
  base="${svg%.svg}"
  w=$(grep -o 'width="[0-9]*"' "$svg" | head -1 | grep -o '[0-9]*')
  h=$(grep -o 'height="[0-9]*"' "$svg" | head -1 | grep -o '[0-9]*')
  html="/tmp/kv_panorama_render.html"
  {
    echo '<html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:#fff}svg{display:block}</style></head><body>'
    cat "$svg"
    echo '</body></html>'
  } > "$html"
  "$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
    --user-data-dir="$PROFILE" --force-device-scale-factor=2 \
    --window-size="$w,$((h + 40))" --screenshot="${base}.png" "file://$html" >/dev/null 2>&1
  echo "rendered $(basename "$base").png (${w}x${h} -> 2x)"
done

# Render with 40 CSS px of slack, then crop it off. This avoids the
# headless-Chrome tiling artifact that appears when the content height
# exactly matches the viewport height.
DIR="$DIR" python3 - <<'PYEOF'
from PIL import Image
import glob, os
root = os.environ["DIR"]
for path in glob.glob(os.path.join(root, "*.png")):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.crop((0, 0, w, h - 80))
    im = im.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                     dither=Image.Dither.NONE)
    im.save(path, optimize=True)
PYEOF
