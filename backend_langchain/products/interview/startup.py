from common.database import apply_column_patches, create_tables
from products.interview.models import INTERVIEW_TABLES

_SESSION_COLUMN_PATCHES = (
    ("user_sessions", "status", "VARCHAR(32) NOT NULL DEFAULT 'completed'"),
    ("user_sessions", "token_estimate", "INT NULL"),
    ("interview_sessions", "status", "VARCHAR(32) NOT NULL DEFAULT 'completed'"),
    ("interview_sessions", "token_estimate", "INT NULL"),
)


async def init_interview_tables() -> None:
    await create_tables(INTERVIEW_TABLES)
    await apply_column_patches(_SESSION_COLUMN_PATCHES)
