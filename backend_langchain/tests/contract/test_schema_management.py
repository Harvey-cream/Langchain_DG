from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, func

from common.database import Base
from common.account.models import User
from products.contract.models import (  # noqa: F401
    AnalysisRunModel,
    ContractModel,
    ContractVersionModel,
    CustomerModel,
    ContractClauseModel,
    ContractReviewSelectionModel,
    ContractRiskModel,
    ContractVersionContentModel,
    CONTRACT_TABLE_NAMES,
)
from products.interview.models import INTERVIEW_TABLES


def _config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


class SchemaManagementTests(unittest.TestCase):
    def test_startup_create_all_excludes_contract_tables(self) -> None:
        startup_table_names = {User.__table__.name}
        startup_table_names.update(table.name for table in INTERVIEW_TABLES)
        self.assertTrue(startup_table_names.isdisjoint(CONTRACT_TABLE_NAMES))
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

    def test_p3_migration_preserves_legacy_runs_clauses_and_risks(self) -> None:
        from products.contract.models import CanonicalContractClauseModel, ContractDocumentBlockModel
        with tempfile.TemporaryDirectory() as temp_dir:
            url = f"sqlite:///{(Path(temp_dir) / 'legacy.sqlite').as_posix()}"
            engine = create_engine(url)
            try:
                User.__table__.create(engine)
                config = _config(url)
                command.upgrade(config, "0002_contract_schema_alignment")
                contract_id, version_id, run_id, clause_id, risk_id = [uuid4() for _ in range(5)]
                with engine.begin() as conn:
                    conn.execute(User.__table__.insert().values(user_id=1, email='migration@test.invalid', username='test', password='test'))
                    conn.execute(CustomerModel.__table__.insert().values(id=1, user_id=1, name='test', email='test@test.invalid'))
                    conn.execute(ContractModel.__table__.insert().values(id=contract_id, user_id=1, customer_id=1, title='test'))
                    conn.execute(ContractVersionModel.__table__.insert().values(id=version_id, contract_id=contract_id,
                        number=1, filename='old.docx', source_key='old'))
                    conn.execute(AnalysisRunModel.__table__.insert().values(id=run_id, version_id=version_id,
                        status='completed', result={'summary': 'historical review'}))
                    conn.execute(ContractClauseModel.__table__.insert().values(id=clause_id, version_id=version_id,
                        run_id=run_id, sequence=1, title='old clause', clause_type='other', original_text='old source'))
                    conn.execute(ContractRiskModel.__table__.insert().values(id=risk_id, version_id=version_id,
                        run_id=run_id, clause_id=clause_id, title='old risk', risk_level='low',
                        evidence_text='old source', reason='old reason', suggestion='old suggestion'))
                    tables = [AnalysisRunModel.__table__, ContractClauseModel.__table__, ContractRiskModel.__table__]
                    before = [conn.execute(select(table)).mappings().all() for table in tables]
                command.upgrade(config, "head")
                with engine.connect() as conn:
                    assert before == [conn.execute(select(table)).mappings().all() for table in tables]
                    for model in (CanonicalContractClauseModel, ContractDocumentBlockModel):
                        assert conn.scalar(select(func.count()).select_from(model)) == 0
                command.downgrade(config, "0002_contract_schema_alignment")
                with engine.connect() as conn:
                    assert before == [conn.execute(select(table)).mappings().all() for table in tables]
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
