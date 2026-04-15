#!/usr/bin/env bash
# 仓库根目录执行：bash build_fronted.sh
# 使用本机 Node/npm构建 frontend_langchain/dist，供 nginx 容器挂载（见 docker-compose 中 ./frontend_langchain/dist）。
# 需要 Node >= 18（Vite 5）。可选：NPM_CONFIG_REGISTRY、NODE_OPTIONS
# CRLF：sed -i 's/\r$//' build_fronted.sh && chmod +x build_fronted.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/frontend_langchain"

command -v node >/dev/null 2>&1 || { echo "错误: 未找到 node"; exit 1; }
major="$(node -p "parseInt(process.versions.node.split('.')[0],10)")"
if [ "$major" -lt 18 ]; then
  echo "错误: 需要 Node >= 18，当前 $(node -v)"
  exit 1
fi

export NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-https://registry.npmmirror.com}"
export NPM_CONFIG_PROGRESS="${NPM_CONFIG_PROGRESS:-false}"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536 --unhandled-rejections=strict}"

echo "==> node $(node -v) registry=$NPM_CONFIG_REGISTRY"
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi
npm run build

if [ ! -f dist/index.html ]; then
  echo "错误: 未生成 dist/index.html"
  exit 1
fi

echo "==> 完成: $ROOT/frontend_langchain/dist（nginx 挂载此目录）"
du -sh dist 2>/dev/null || true
