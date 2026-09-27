#!/usr/bin/env bash
#
# 批量无损/近无损压缩 static/images 下的 PNG 与 JPG 图片（原地覆盖）。
# 依赖：pngquant、jpegoptim
#   macOS:  brew install pngquant jpegoptim
#   Ubuntu: sudo apt-get install pngquant jpegoptim
#
# 用法：
#   ./scripts/optimize-images.sh            # 压缩 static/images 全部图片
#   ./scripts/optimize-images.sh path/dir   # 只压缩指定目录
#
# 说明：图片受 git 跟踪，压缩结果可通过 `git checkout` 还原。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-$ROOT_DIR/static/images}"

if ! command -v pngquant >/dev/null 2>&1; then
  echo "[error] 未找到 pngquant，请先安装：brew install pngquant" >&2
  exit 1
fi
if ! command -v jpegoptim >/dev/null 2>&1; then
  echo "[error] 未找到 jpegoptim，请先安装：brew install jpegoptim" >&2
  exit 1
fi

echo "==> 目标目录: $TARGET_DIR"

before=$(du -sh "$TARGET_DIR" | cut -f1)

# PNG：调色板量化，质量区间 65-90，原地覆盖
find "$TARGET_DIR" -type f -iname '*.png' -print0 \
  | xargs -0 -I{} pngquant --force --skip-if-larger --quality=65-90 --strip --output "{}" -- "{}" \
  || true   # pngquant 对已优化文件返回非零码，忽略

# JPG：最高质量 85，去除元数据，原地覆盖
find "$TARGET_DIR" -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) -print0 \
  | xargs -0 jpegoptim --max=85 --strip-all --all-progressive

after=$(du -sh "$TARGET_DIR" | cut -f1)

echo "==> 完成。压缩前: $before  ->  压缩后: $after"
