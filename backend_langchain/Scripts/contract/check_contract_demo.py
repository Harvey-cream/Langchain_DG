"""Read-only checks; never print credentials or document contents."""
import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import text
from common.database import engine
from common.settings import oss_config, llm_config


async def main():
    print('OSS configured:', all(oss_config()[k] for k in ('access_key_id', 'access_key_secret', 'bucket_name', 'endpoint')))
    print('LLM configured:', bool(llm_config()['api_key']))
    try:
        async with engine.connect() as connection:
            print('Database reachable:', await connection.scalar(text('SELECT 1')) == 1)
    except Exception as exc:
        print('Database unavailable:', type(exc).__name__)
        raise SystemExit(1)
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
