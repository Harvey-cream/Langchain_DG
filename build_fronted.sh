#!/usr/bin/env bash
# 在服务器上拉代码后执行：bash build_fronted.sh
# npm run build = tsc + vite build，产出可部署的静态站点（HTML/JS/CSS/资源）到 frontend_langchain/dist，供 nginx root 使用
# 使用 npmmirror + 控制 Node 堆内存，减轻小内存机器 OOM
# 若从 Windows 检出为 CRLF 导致报错，可先：sed -i 's/\r$//' build_fronted.sh && chmod +x build_fronted.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT/frontend_langchain"

# 1核2G 等环境可调低，如 768；内存更大可设为 3072
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536}"

export NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-https://registry.npmmirror.com}"
export NPM_CONFIG_PROGRESS="${NPM_CONFIG_PROGRESS:-false}"

echo "==> registry: $NPM_CONFIG_REGISTRY"
echo "==> NODE_OPTIONS: $NODE_OPTIONS"

if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund
else
  echo "==> 无 package-lock.json，使用 npm install"
  npm install --no-audit --no-fund
fi

echo "==> 构建静态资源到 dist/ ..."
npm run build

echo "==> 静态文件已生成: $ROOT/frontend_langchain/dist"
du -sh dist 2>/dev/null || true
