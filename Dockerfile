# 后端：Django + LangChain（构建上下文为仓库根目录）
# pip默认阿里云；apt 见下方 RUN。torch+cpu 仍走 requirements 里 PyTorch 官方 cpu 索引。
FROM python:3.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=backend_langchain.settings \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_TRUSTED_HOST="mirrors.aliyun.com download.pytorch.org"

WORKDIR /app

# Debian bookworm：国内 apt镜像（构建失败可改回官方源）
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g; s|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i 's/deb.debian.org/mirrors.aliyun.com/g; s/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
      default-libmysqlclient-dev \
      pkg-config \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend_langchain/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY backend_langchain/ /app/

RUN mkdir -p /app/common/data

EXPOSE 8000
# 迁移请自行执行：docker compose exec backend python manage.py migrate
CMD ["gunicorn", "backend_langchain.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-"]
