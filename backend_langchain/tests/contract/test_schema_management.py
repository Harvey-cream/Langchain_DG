from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.db import CONTRACT_TABLE_NAMES, _legacy_tables
from app.models import Base, User
from infrastructure.db.models.analysis import AnalysisRunModel  # noqa: F401
from infrastructure.db.models.contract import ContractModel  # noqa: F401
from infrastructure.db.models.customer import CustomerModel  # noqa: F401
from infrastructure.db.models.review import (  # noqa: F401
    ContractClauseModel,
    ContractReviewSelectionModel,
    ContractRiskModel,
    ContractVersionContentModel,
)
from infrastructure.db.models.version import ContractVersionModel  # noqa: F401


def _config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


class SchemaManagementTests(unittest.TestCase):
    def test_startup_create_all_excludes_contract_tables(self) -> None:
        self.assertTrue(
            {table.name for table in _legacy_tables(Base.metadata)}.isdisjoint(
                CONTRACT_TABLE_NAMES
            )
        )
        self.assertTrue(CONTRACT_TABLE_NAMES.issubset(Base.metadata.tables))

    def test_baseline_migrates_fresh_database_and_downgrades(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "contract-migration.sqlite"
            database_url = f"sqlite:///{path.as_posix()}"
            engine = create_engine(database_url)
            try:
                # users is a legacy-owned prerequisite for two Contract foreign keys.
                User.__table__.create(engine)

                config = _config(database_url)
                command.upgrade(config, "head")

                inspector = inspect(engine)
                self.assertTrue(CONTRACT_TABLE_NAMES.issubset(inspector.get_table_names()))
                unique_constraints = {
                    tuple(item["column_names"])
                    for item in inspector.get_unique_constraints("contract_versions")
                }
                self.assertIn(("contract_id", "number"), unique_constraints)
                active = next(
                    item
                    for item in inspector.get_indexes("contract_analysis_runs")
                    if item["name"] == "uq_contract_active_analysis"
                )
                self.assertTrue(active["unique"])

                command.downgrade(config, "base")
                remaining = set(inspect(engine).get_table_names())
                self.assertTrue(remaining.isdisjoint(CONTRACT_TABLE_NAMES))
                self.assertIn("users", remaining)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
