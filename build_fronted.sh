#!/usr/bin/env bash
# 在仓库根目录执行：bash build_fronted.sh
# 产出 frontend_langchain/dist 供 nginx 挂载。
#
# - 宿主机 Node >= 18：本地 npm构建。
# - CentOS 7 等（glibc 2.17）无法装 Node 20 rpm：若已装 Docker，会自动用 node:20 容器构建；
#   也可强制：BUILD_FRONTEND_USE_DOCKER=1 bash build_fronted.sh
#   若不要用容器：BUILD_FRONTEND_USE_DOCKER=0 bash build_fronted.sh
#
# 若从 Windows 检出 CRLF：sed -i 's/\r$//' build_fronted.sh && chmod +x build_fronted.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT/frontend_langchain"
NODE_IMG="${BUILD_FRONTEND_NODE_IMAGE:-node:20-bookworm-slim}"

_node_major() {
  if ! command -v node >/dev/null 2>&1; then
    echo 0
    return
  fi
  node -p "parseInt(process.versions.node.split('.')[0], 10)" 2>/dev/null || echo 0
}

_use_docker_build() {
  if [ "${BUILD_FRONTEND_USE_DOCKER:-}" = "1" ]; then
    return 0
  fi
  if [ "${BUILD_FRONTEND_USE_DOCKER:-}" = "0" ]; then
    return 1
  fi
  command -v docker >/dev/null 2>&1 || return 1
  local m
  m="$(_node_major)"
  if [ "$m" -lt 18 ]; then
    return 0
  fi
  return 1
}

if _use_docker_build; then
  echo "==> 使用 Docker 镜像 ${NODE_IMG} 构建（宿主机 Node 不足 18 或 BUILD_FRONTEND_USE_DOCKER=1）"
  echo "==> 挂载: ${FRONTEND_DIR} -> /app"
  docker pull "${NODE_IMG}"
  docker run --rm \
    -e NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-https://registry.npmmirror.com}" \
    -e NPM_CONFIG_PROGRESS="${NPM_CONFIG_PROGRESS:-false}" \
    -e NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536}" \
    -v "${FRONTEND_DIR}:/app" \
    -w /app \
    "${NODE_IMG}" \
    bash -lc 'set -euo pipefail; node -v; if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi; npm run build'
  echo "==> 静态文件已生成: ${FRONTEND_DIR}/dist"
  du -sh "${FRONTEND_DIR}/dist" 2>/dev/null || true
  echo "==> docker compose：在仓库根目录 up；nginx 挂载 ./frontend_langchain/dist"
  exit 0
fi

cd "$FRONTEND_DIR"

# Vite 5 需要 Node >= 18
if ! command -v node >/dev/null 2>&1; then
  echo "错误: 未找到 node，且未使用 Docker 构建（可安装 Docker 后重试，或设置 BUILD_FRONTEND_USE_DOCKER=1）"
  exit 1
fi
NODE_MAJOR="$(_node_major)"
if [ "$NODE_MAJOR" -lt 18 ]; then
  echo "错误: 当前 Node $(node -v)，需要 >= 18（Vite 5）。"
  echo "CentOS 7 / glibc 2.17 无法通过 yum 安装官方 Node 20，可："
  echo "  1) 已装 Docker 时直接: bash build_fronted.sh（会自动用容器构建）"
  echo "  2) 或: BUILD_FRONTEND_USE_DOCKER=1 bash build_fronted.sh"
  echo "  3) 或换 glibc≥2.28 的系统 /用 nvm 源码编译 Node（较慢）"
  exit 1
fi

export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=1536}"
export NPM_CONFIG_REGISTRY="${NPM_CONFIG_REGISTRY:-https://registry.npmmirror.com}"
export NPM_CONFIG_PROGRESS="${NPM_CONFIG_PROGRESS:-false}"

echo "==> node: $(node -v)"
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

echo "==> 静态文件已生成: $FRONTEND_DIR/dist"
du -sh dist 2>/dev/null || true
echo "==> docker compose：请在仓库根目录执行 up；nginx 挂载的是上述 dist"
