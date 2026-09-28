from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException

from products.contract import api as contract_router
from products.contract import db as contract_db
from products.contract.models import ContractVersionModel
from products.contract.domain.review import ReviewContext
from products.contract.schemas import (
    ContractCreate,
    ContractVersionCreate,
    CustomerCreate,
)
from products.contract.schemas.analysis import ContractAnalysis
from products.contract.workflows.review_workflow import run_contract_review


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Transaction:
    def __init__(self, events: list[str] | None = None):
        self.events = events

    async def __aenter__(self):
        if self.events is not None:
            self.events.append("tx.begin")
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.events is not None:
            self.events.append("tx.rollback" if exc_type else "tx.commit")
        return False


class _FakeSession:
    def __init__(self, *, scalar_results=(), events: list[str] | None = None):
        self.scalar_results = list(scalar_results)
        self.events = events
        self.added: list[object] = []
        self.scalar_calls = 0
        self.execute = AsyncMock()
        self.scalars = AsyncMock()
        self.rollback = AsyncMock()

    def begin(self):
        return _Transaction(self.events)

    def in_transaction(self):
        return False

    async def scalar(self, _statement):
        self.scalar_calls += 1
        if self.events is not None:
            self.events.append("db.scalar")
        if not self.scalar_results:
            raise AssertionError("unexpected scalar query")
        return self.scalar_results.pop(0)

    def add(self, value):
        self.added.append(value)
        if self.events is not None:
            self.events.append("db.add")

    def add_all(self, values):
        self.added.extend(values)
        if self.events is not None:
            self.events.append("db.add_all")

    async def flush(self):
        if self.events is not None:
            self.events.append("db.flush")

    async def delete(self, value):
        if self.events is not None:
            self.events.append("db.delete")
        self.deleted = value


class _UploadFile:
    def __init__(self, filename="contract.pdf", data=b"%PDF-test"):
        self.filename = filename
        self.data = data
        self.closed = False

    async def read(self, _limit):
        return self.data

    async def close(self):
        self.closed = True


class ContractRouterBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_keeps_oss_outside_transaction_and_enqueues_after_commit(self):
        events: list[str] = []
        session = _FakeSession(
            scalar_results=(uuid4(), object(), 0),
            events=events,
        )
        contract_id = uuid4()
        background = BackgroundTasks()
        file = _UploadFile(filename="folder/contract.pdf")
        storage = SimpleNamespace(
            put=MagicMock(side_effect=lambda *_args, **_kwargs: events.append("oss.put")),
            delete=MagicMock(side_effect=lambda *_args: events.append("oss.delete")),
        )

        with (
            patch.object(contract_router, "OssObjectStorage", return_value=storage),
            patch.object(contract_router, "validate_file", return_value="pdf"),
        ):
            await contract_router.upload(
                contract_id,
                background,
                file,
                SimpleNamespace(user_id=7),
                session,
            )

        self.assertEqual(
            events,
            [
                "tx.begin",
                "db.scalar",
                "tx.commit",
                "oss.put",
                "tx.begin",
                "db.scalar",
                "db.scalar",
                "db.add_all",
                "db.flush",
                "tx.commit",
            ],
        )
        version, run = session.added
        self.assertEqual(version.contract_id, contract_id)
        self.assertEqual(version.number, 1)
        self.assertEqual(run.version_id, version.id)
        self.assertTrue(file.closed)
        self.assertEqual(len(background.tasks), 1)
        task = background.tasks[0]
        self.assertIs(task.func, contract_router.execute_analysis)
        self.assertEqual(task.args, (run.id,))

    async def test_upload_rechecks_ownership_and_deletes_oss_on_database_failure(self):
        session = _FakeSession(scalar_results=(uuid4(), None))
        storage = SimpleNamespace(put=MagicMock(), delete=MagicMock())
        background = BackgroundTasks()

        with (
            patch.object(contract_router, "OssObjectStorage", return_value=storage),
            patch.object(contract_router, "validate_file", return_value="pdf"),
        ):
            with self.assertRaises(HTTPException) as raised:
                await contract_router.upload(
                    uuid4(),
                    background,
                    _UploadFile(),
                    SimpleNamespace(user_id=7),
                    session,
                )

        self.assertEqual(raised.exception.status_code, 404)
        storage.put.assert_called_once()
        storage.delete.assert_called_once()
        self.assertEqual(len(background.tasks), 0)

    async def test_invalid_upload_has_no_database_or_oss_side_effects(self):
        storage = SimpleNamespace(put=MagicMock(), delete=MagicMock())
        session = _FakeSession()

        with (
            patch.object(contract_router, "OssObjectStorage", return_value=storage),
            patch.object(
                contract_router,
                "validate_file",
                side_effect=ValueError("请上传有效的 PDF 或 DOCX 文件"),
            ),
        ):
            with self.assertRaises(HTTPException) as raised:
                await contract_router.upload(
                    uuid4(),
                    BackgroundTasks(),
                    _UploadFile(data=b"bad"),
                    SimpleNamespace(user_id=7),
                    session,
                )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(session.scalar_calls, 0)
        storage.put.assert_not_called()

    async def test_retry_reuses_active_run_without_enqueuing(self):
        user_id = 7
        contract_id = uuid4()
        version_id = uuid4()
        active = SimpleNamespace(id=uuid4(), attempt=2)
        version = SimpleNamespace(
            id=version_id,
            source_key=f"contracts/{user_id}/{contract_id}/{version_id}/original.pdf",
        )
        background = BackgroundTasks()
        session = _FakeSession(scalar_results=(version, active))

        await contract_router.analyze(
            contract_id,
            version_id,
            background,
            SimpleNamespace(user_id=user_id),
            session,
        )

        self.assertEqual(len(background.tasks), 0)
        self.assertEqual(session.added, [])

    async def test_retry_creates_next_attempt_and_enqueues(self):
        user_id = 7
        contract_id = uuid4()
        version_id = uuid4()
        version = SimpleNamespace(
            id=version_id,
            status="failed",
            source_key=f"contracts/{user_id}/{contract_id}/{version_id}/original.docx",
        )
        background = BackgroundTasks()
        session = _FakeSession(scalar_results=(version, None, 2))

        await contract_router.analyze(
            contract_id,
            version_id,
            background,
            SimpleNamespace(user_id=user_id),
            session,
        )

        run = session.added[0]
        self.assertEqual(run.attempt, 3)
        self.assertEqual(run.version_id, version_id)
        self.assertEqual(version.status, "pending")
        self.assertEqual(background.tasks[0].args, (run.id,))

    async def test_version_endpoint_allocates_number_while_contract_is_locked(self):
        contract_id = uuid4()
        session = _FakeSession(scalar_results=(object(), 2))

        await contract_router.create_contract_version(
            contract_id,
            ContractVersionCreate(
                source_key="oss://contract/v3.pdf",
                filename="v3.pdf",
            ),
            SimpleNamespace(user_id=7),
            session,
        )

        version = session.added[0]
        self.assertEqual(version.number, 3)
        self.assertEqual(version.contract_id, contract_id)

    async def test_whitespace_crud_values_are_rejected_before_database_access(self):
        session = _FakeSession()
        user = SimpleNamespace(user_id=7)

        contract_response = await contract_router.create_contract(
            ContractCreate(customer_id=1, title="   "),
            user,
            session,
        )
        customer_response = await contract_router.create_customer(
            CustomerCreate(name="   ", email="a@b.com"),
            user,
            session,
        )
        version_response = await contract_router.create_contract_version(
            uuid4(),
            ContractVersionCreate(source_key="   ", filename="v1.pdf"),
            user,
            session,
        )

        self.assertEqual(contract_response.status_code, 400)
        self.assertEqual(customer_response.status_code, 400)
        self.assertEqual(version_response.status_code, 400)
        self.assertEqual(session.scalar_calls, 0)


class WorkflowClaimBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_executors_only_review_claimed_run_once(self):
        context = ReviewContext(uuid4(), uuid4(), "key", "contract.docx")
        lock = asyncio.Lock()
        claimed = False

        async def claim(_session, _run_id):
            nonlocal claimed
            async with lock:
                if claimed:
                    return None
                claimed = True
                return context

        completed = AsyncMock()
        failed = AsyncMock()
        reviewer = SimpleNamespace(
            review=AsyncMock(
                return_value=ContractAnalysis(document_type="合同", summary="摘要")
            )
        )
        pipeline = SimpleNamespace(
            ensure=AsyncMock(
                return_value=SimpleNamespace(
                    document=SimpleNamespace(document_text="真实合同条款")
                )
            )
        )
        with (
            patch.object(contract_db, "claim_run", side_effect=claim),
            patch.object(contract_db, "mark_parsing", AsyncMock()),
            patch.object(contract_db, "mark_analyzing", AsyncMock()),
            patch.object(contract_db, "complete_run", completed),
            patch.object(contract_db, "fail_run", failed),
        ):
            session = _FakeSession()
            await asyncio.gather(
                run_contract_review(session, pipeline, reviewer, context.run_id),
                run_contract_review(session, pipeline, reviewer, context.run_id),
            )

        reviewer.review.assert_awaited_once()
        completed.assert_awaited_once()
        failed.assert_not_awaited()


class HistoryAndIsolationBehaviorTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _run(*, version_id, status="completed", result=None, attempt=1):
        return SimpleNamespace(
            id=uuid4(),
            version_id=version_id,
            status=status,
            current_step="review_required" if status == "completed" else status,
            attempt=attempt,
            result=result if result is not None else {"summary": "ok"},
            error=None,
            model_name="test-model",
            prompt_version="v2",
            created_at=None,
            started_at=None,
            finished_at=None,
        )

    async def test_history_returns_multiple_runs(self):
        version_id = uuid4()
        rows = [
            self._run(version_id=version_id, attempt=2),
            self._run(version_id=version_id, status="failed", result=None, attempt=1),
        ]
        session = _FakeSession()
        session.scalars.return_value = _Result(rows)

        with patch.object(
            contract_db, "_get_owned_version", AsyncMock(return_value=object())
        ):
            history = await contract_db.list_history(
                session, 7, uuid4(), version_id
            )

        self.assertEqual([item.attempt for item in history], [2, 1])

    async def test_select_accepts_only_completed_run_for_same_version(self):
        version_id = uuid4()
        completed = self._run(version_id=version_id)
        session = _FakeSession(scalar_results=[completed])

        with patch.object(
            contract_db, "_get_owned_version", AsyncMock(return_value=object())
        ):
            selected = await contract_db.select_run(
                session, 7, uuid4(), version_id, completed.id
            )

        self.assertTrue(selected)
        session.execute.assert_awaited_once()

    async def test_user_cannot_read_or_select_unowned_version(self):
        session = _FakeSession()

        with patch.object(
            contract_db, "_get_owned_version", AsyncMock(return_value=None)
        ):
            self.assertIsNone(
                await contract_db.load_snapshot(session, 8, uuid4(), uuid4())
            )
            self.assertIsNone(
                await contract_db.list_history(session, 8, uuid4(), uuid4())
            )
            self.assertFalse(
                await contract_db.select_run(
                    session, 8, uuid4(), uuid4(), uuid4()
                )
            )

        session.execute.assert_not_awaited()


class SchemaSafetyBehaviorTests(unittest.TestCase):
    def test_contract_schema_is_not_initialized_at_application_startup(self):
        import inspect

        from app import main as app_main
        from common import database

        create_source = inspect.getsource(database.create_tables)
        startup_source = inspect.getsource(app_main.lifespan)
        self.assertIn("tables=selected", create_source)
        self.assertIn("create_tables([User.__table__])", startup_source)
        self.assertIn("init_interview_tables()", startup_source)
        self.assertNotIn("CONTRACT_TABLES", startup_source)

    def test_version_model_declares_unique_contract_number_constraint(self):
        constraints = {
            constraint.name
            for constraint in ContractVersionModel.__table__.constraints
            if constraint.name
        }
        self.assertIn("uq_contract_version_number", constraints)


if __name__ == "__main__":
    unittest.main()
