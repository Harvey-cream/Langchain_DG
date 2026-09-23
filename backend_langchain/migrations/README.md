# Contract Schema migration

`alembic/` is the authoritative schema history for the eight Contract Review tables.
The older `0001_contract_schema.py` file is retained only as historical evidence and is
not a migration runner.

## Fresh database

The Contract schema references `users.user_id`, which remains owned by the legacy
application bootstrap. Create the legacy tables first, then run:

```powershell
.\.venv-py312\Scripts\python.exe -c "import asyncio; from app.db import init_db_tables; asyncio.run(init_db_tables())"
.\.venv-py312\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Application startup no longer creates or alters Contract tables. Deployments must run
the Alembic command before starting the API.

## Existing database baseline

Do not run `upgrade` against tables created by the old startup path. First run the
read-only audit:

```powershell
.\.venv-py312\Scripts\python.exe scripts\audit_contract_schema.py --target baseline
```

Only when `ok` is `true`, the reported data checks are empty, and the real target
database has been independently confirmed, mark it as the baseline:

```powershell
.\.venv-py312\Scripts\python.exe -m alembic -c alembic.ini stamp 0001_contract_review_baseline
.\.venv-py312\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\.venv-py312\Scripts\python.exe scripts\audit_contract_schema.py --target head
```

The `0002` migration normalizes the legacy duplicate uniqueness objects without a
data rewrite and adds the ORM-declared status index. If either audit reports a
mismatch, stop and review it. Never stamp a mismatched database and never repair
production data from this audit script.
