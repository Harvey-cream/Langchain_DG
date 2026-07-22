from pathlib import Path

raw = Path(".env").read_text(encoding="utf-8")
vals: dict[str, str] = {}
for line in raw.splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        continue
    k, _, v = s.partition("=")
    if not all(c.isalnum() or c == "_" for c in k):
        continue
    if k.startswith(
        ("OSS_", "OPENAI_", "DASH", "APP_", "MYSQL_", "REDIS_", "HF_")
    ):
        vals[k] = v

lines = [
    "# Root .env (do not commit). Copy from .env.example.",
    "# Secrets injected into backend_langchain/env/settings_*.yaml via ${VAR}.",
    "",
    f"APP_ENV={vals.get('APP_ENV', 'debug')}",
    "",
    "# LLM",
    f"OPENAI_BASE_URL={vals.get('OPENAI_BASE_URL', '')}",
    f"OPENAI_API_KEY={vals.get('OPENAI_API_KEY', '')}",
    f"OPENAI_MODEL={vals.get('OPENAI_MODEL', 'gpt-5.4')}",
    "",
    "# DashScope embedding",
    f"DASHSCOPE_API_KEY={vals.get('DASHSCOPE_API_KEY', '')}",
    f"DASHSCOPE_EMBEDDING_MODEL={vals.get('DASHSCOPE_EMBEDDING_MODEL', 'text-embedding-v3')}",
    "",
    "# App",
    f"APP_SECRET_KEY={vals.get('APP_SECRET_KEY', '')}",
    f"APP_ALLOWED_HOST={vals.get('APP_ALLOWED_HOST', '')}",
    "",
    "# MySQL",
    f"MYSQL_ROOT_PASSWORD={vals.get('MYSQL_ROOT_PASSWORD', '')}",
    f"MYSQL_PASSWORD={vals.get('MYSQL_PASSWORD', '')}",
    f"MYSQL_DATABASE={vals.get('MYSQL_DATABASE', 'langchain')}",
    f"MYSQL_PUBLISH_PORT={vals.get('MYSQL_PUBLISH_PORT', '3307')}",
    f"REDIS_PUBLISH_PORT={vals.get('REDIS_PUBLISH_PORT', '6379')}",
    "",
    "# Optional local MySQL overrides",
    "# MYSQL_HOST=localhost",
    "# MYSQL_PORT=3306",
    "",
    "# SKIP_RAG_STARTUP_WARMUP=1",
    f"HF_ENDPOINT={vals.get('HF_ENDPOINT', 'https://hf-mirror.com')}",
    "",
    "# Aliyun OSS (agent knowledge upload)",
    f"OSS_ACCESS_KEY_ID={vals.get('OSS_ACCESS_KEY_ID', '')}",
    f"OSS_ACCESS_KEY_SECRET={vals.get('OSS_ACCESS_KEY_SECRET', '')}",
    f"OSS_BUCKET_NAME={vals.get('OSS_BUCKET_NAME', 'my-oss-bucket-2026-2026')}",
    f"OSS_ENDPOINT={vals.get('OSS_ENDPOINT', 'oss-cn-shenzhen.aliyuncs.com')}",
    f"OSS_PREFIX={vals.get('OSS_PREFIX', 'agent-kb')}",
    f"OSS_URL_PREFIX={vals.get('OSS_URL_PREFIX', '')}",
    "",
]
Path(".env").write_text("\n".join(lines), encoding="utf-8")

from dotenv import dotenv_values

v = dotenv_values(".env")
print("parsed", len(v), "OSS", bool(v.get("OSS_ACCESS_KEY_ID")), "OPENAI", bool(v.get("OPENAI_API_KEY")))
Path("_env_preview.txt").unlink(missing_ok=True)
