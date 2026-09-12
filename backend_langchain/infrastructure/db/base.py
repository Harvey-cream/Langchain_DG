"""业务库共享 DeclarativeBase。

`app.models` 与 contract 持久化模型位于同一 PostgreSQL 库，彼此存在跨模块外键
（如 `contracts.user_id -> users.user_id`）。若各用独立的 DeclarativeBase，
SQLAlchemy 在 flush 前为表排序时会解析不到外键目标表，抛 `NoReferencedTableError`。
因此全库共用同一 MetaData。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
