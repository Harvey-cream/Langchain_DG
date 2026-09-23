from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import BackgroundTasks
from infrastructure.db.models.version import ContractVersionModel
from infrastructure.db.repositories.contract_review_store import (
    SqlAlchemyContractReviewStore,
)
from infrastructure.document.contract_parser import validate_file
from infrastructure.queue.background_tasks import FastApiBackgroundJobDispatcher
from products.contract.domain.review import ReviewContext, VersionContent
from products.contract.application.review_service import (
    AnalysisRunNotSelectableError,
    ContractNotFoundError,
    ContractReviewService,
    ContractVersionNotFoundError,
)
from products.contract.application.services import ContractVersionApplicationService
from products.contract.schemas.analysis import ContractAnalysis
from products.contract.workflows.review_workflow import ContractReviewWorkflow


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, *, scalar_results=(), commit_error: Exception | None = None):
        self.scalar_results = list(scalar_results)
        self.commit_error = commit_error
        self.added: list[object] = []
        self.execute = AsyncMock()
        self.flush = AsyncMock()
        self.rollback = AsyncMock()
        self.commit = AsyncMock(side_effect=commit_error)
        self.scalars = AsyncMock()

    async def scalar(self, _statement):
        if not self.scalar_results:
            raise AssertionError("unexpected scalar query")
        return self.scalar_results.pop(0)

    def add(self, value):
        self.added.append(value)


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _ServiceSession:
    def __init__(self):
        self.begin_count = 0

    def begin(self):
        self.begin_count += 1
        return _Transaction()


class ContractReviewServiceTests(unittest.IsolatedAsyncioTestCase):
    def _service(self, store):
        session = _ServiceSession()
        storage = SimpleNamespace(put=MagicMock(), delete=MagicMock())
        dispatcher = SimpleNamespace(dispatch_analysis=AsyncMock())
        service = ContractReviewService(
            session=session,
            store=store,
            storage=storage,
            validate_upload=lambda _name, _data: "pdf",
            dispatcher=dispatcher,
        )
        return service, session, storage, dispatcher

    async def test_upload_is_a_single_service_use_case(self):
        contract_id = uuid4()
        run = SimpleNamespace(id=uuid4())
        version = SimpleNamespace(id=uuid4(), number=1)
        store = SimpleNamespace(
            get_owned_contract=AsyncMock(return_value=object()),
            lock_owned_contract=AsyncMock(return_value=object()),
            get_next_version_number=AsyncMock(return_value=1),
            create_version=AsyncMock(return_value=version),
            create_run=AsyncMock(return_value=run),
        )
        service, session, storage, dispatcher = self._service(store)

        actual_version, actual_run = await service.upload_contract_version(
            user_id=7,
            contract_id=contract_id,
            filename="folder/contract.pdf",
            data=b"%PDF-test",
        )

        self.assertIs(actual_version, version)
        self.assertIs(actual_run, run)
        self.assertEqual(session.begin_count, 2)
        storage.put.assert_called_once()
        store.lock_owned_contract.assert_awaited_once_with(7, contract_id)
        dispatcher.dispatch_analysis.assert_awaited_once_with(run.id)

    async def test_upload_rechecks_ownership_after_oss_and_compensates(self):
        store = SimpleNamespace(
            get_owned_contract=AsyncMock(return_value=object()),
            lock_owned_contract=AsyncMock(return_value=None),
        )
        service, _session, storage, dispatcher = self._service(store)

        with self.assertRaises(ContractNotFoundError):
            await service.upload_contract_version(
                user_id=7,
                contract_id=uuid4(),
                filename="contract.pdf",
                data=b"%PDF-test",
            )

        storage.put.assert_called_once()
        storage.delete.assert_called_once()
        dispatcher.dispatch_analysis.assert_not_awaited()

    async def test_oss_upload_happens_without_contract_lock_or_open_transaction(self):
        events: list[str] = []
        contract_id = uuid4()
        run = SimpleNamespace(id=uuid4())
        version = SimpleNamespace(id=uuid4(), number=1)

        class RecordingTransaction:
            async def __aenter__(self):
                events.append("tx.begin")

            async def __aexit__(self, exc_type, exc, tb):
                events.append("tx.rollback" if exc_type else "tx.commit")

        class RecordingSession:
            def begin(self):
                return RecordingTransaction()

        async def record(name, value):
            events.append(name)
            return value

        store = SimpleNamespace(
            get_owned_contract=lambda *_: record("contract.read", object()),
            lock_owned_contract=lambda *_: record("contract.lock", object()),
            get_next_version_number=lambda *_: record("version.number", 1),
            create_version=lambda **_: record("version.create", version),
            create_run=lambda **_: record("run.create", run),
        )

        class RecordingStorage:
            def put(self, *_args, **_kwargs):
                events.append("oss.put")

            def delete(self, _key):
                events.append("oss.delete")

        async def dispatch(_run_id):
            events.append("job.dispatch")

        service = ContractReviewService(
            session=RecordingSession(),
            store=store,
            storage=RecordingStorage(),
            validate_upload=lambda _name, _data: "pdf",
            dispatcher=SimpleNamespace(dispatch_analysis=dispatch),
        )

        await service.upload_contract_version(
            user_id=7,
            contract_id=contract_id,
            filename="contract.pdf",
            data=b"%PDF-test",
        )

        self.assertEqual(
            events,
            [
                "tx.begin",
                "contract.read",
                "tx.commit",
                "oss.put",
                "tx.begin",
                "contract.lock",
                "version.number",
                "version.create",
                "run.create",
                "tx.commit",
                "job.dispatch",
            ],
        )

    async def test_retry_reuses_active_run_without_dispatch(self):
        contract_id = uuid4()
        version_id = uuid4()
        active = SimpleNamespace(id=uuid4(), attempt=2)
        version = SimpleNamespace(
            id=version_id,
            source_key=f"contracts/7/{contract_id}/{version_id}/original.pdf",
        )
        store = SimpleNamespace(
            lock_owned_version=AsyncMock(return_value=version),
            get_active_run=AsyncMock(return_value=active),
        )
        service, _session, _storage, dispatcher = self._service(store)

        run, created = await service.retry_analysis(
            user_id=7,
            contract_id=contract_id,
            version_id=version_id,
        )

        self.assertIs(run, active)
        self.assertFalse(created)
        dispatcher.dispatch_analysis.assert_not_awaited()

    async def test_query_history_and_selection_use_business_errors(self):
        store = SimpleNamespace(
            load_snapshot=AsyncMock(return_value=None),
            list_history=AsyncMock(return_value=None),
            select_run=AsyncMock(return_value=False),
        )
        service, _session, _storage, _dispatcher = self._service(store)
        args = dict(user_id=7, contract_id=uuid4(), version_id=uuid4())

        with self.assertRaises(ContractVersionNotFoundError):
            await service.get_analysis(**args)
        with self.assertRaises(ContractVersionNotFoundError):
            await service.get_analysis_history(**args)
        with self.assertRaises(AnalysisRunNotSelectableError):
            await service.select_analysis_run(**args, run_id=uuid4())


class ServiceMutationBehaviorTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _service(store, *, validator=lambda _name, _data: "pdf"):
        storage = SimpleNamespace(put=MagicMock(), delete=MagicMock())
        dispatcher = SimpleNamespace(dispatch_analysis=AsyncMock())
        service = ContractReviewService(
            session=_ServiceSession(),
            store=store,
            storage=storage,
            validate_upload=validator,
            dispatcher=dispatcher,
        )
        return service, storage, dispatcher

    async def test_version_numbers_follow_locked_store_allocator(self):
        contract_id = uuid4()
        numbers = iter((1, 2, 3))

        async def create_version(**kwargs):
            return SimpleNamespace(**kwargs)

        store = SimpleNamespace(
            get_owned_contract=AsyncMock(return_value=object()),
            lock_owned_contract=AsyncMock(return_value=object()),
            get_next_version_number=AsyncMock(side_effect=lambda _id: next(numbers)),
            create_version=create_version,
            create_run=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
        )
        service, _storage, _dispatcher = self._service(store)

        created = []
        for _ in range(3):
            version, _run = await service.upload_contract_version(
                user_id=7,
                contract_id=contract_id,
                filename="contract.pdf",
                data=b"%PDF-test",
            )
            created.append(version.number)

        self.assertEqual(created, [1, 2, 3])
        self.assertEqual(store.lock_owned_contract.await_count, 3)

    async def test_invalid_upload_has_no_database_or_oss_side_effects(self):
        store = SimpleNamespace(get_owned_contract=AsyncMock())
        service, storage, dispatcher = self._service(store, validator=validate_file)

        with self.assertRaises(ValueError):
            await service.upload_contract_version(
                user_id=7,
                contract_id=uuid4(),
                filename="bad.pdf",
                data=b"not-a-pdf",
            )

        store.get_owned_contract.assert_not_awaited()
        storage.put.assert_not_called()
        dispatcher.dispatch_analysis.assert_not_awaited()

    async def test_database_failure_compensates_uploaded_oss_object(self):
        store = SimpleNamespace(
            get_owned_contract=AsyncMock(return_value=object()),
            lock_owned_contract=AsyncMock(return_value=object()),
            get_next_version_number=AsyncMock(return_value=1),
            create_version=AsyncMock(return_value=SimpleNamespace(id=uuid4())),
            create_run=AsyncMock(side_effect=RuntimeError("database unavailable")),
        )
        service, storage, dispatcher = self._service(store)

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await service.upload_contract_version(
                user_id=7,
                contract_id=uuid4(),
                filename="contract.pdf",
                data=b"%PDF-test",
            )

        storage.put.assert_called_once()
        storage.delete.assert_called_once()
        dispatcher.dispatch_analysis.assert_not_awaited()

    async def test_retry_without_active_run_increments_attempt(self):
        contract_id = uuid4()
        version_id = uuid4()
        version = SimpleNamespace(
            id=version_id,
            status="failed",
            source_key=f"contracts/7/{contract_id}/{version_id}/original.pdf",
        )
        run = SimpleNamespace(id=uuid4(), attempt=3, status="pending")
        store = SimpleNamespace(
            lock_owned_version=AsyncMock(return_value=version),
            get_active_run=AsyncMock(return_value=None),
            get_max_attempt=AsyncMock(return_value=2),
            create_run=AsyncMock(return_value=run),
            set_version_status=AsyncMock(),
        )
        service, _storage, dispatcher = self._service(store)

        actual, created = await service.retry_analysis(
            user_id=7,
            contract_id=contract_id,
            version_id=version_id,
        )

        self.assertIs(actual, run)
        self.assertTrue(created)
        store.create_run.assert_awaited_once_with(
            version_id=version_id,
            attempt=3,
            prompt_version="v2",
        )
        store.set_version_status.assert_awaited_once_with(version, "pending")
        dispatcher.dispatch_analysis.assert_awaited_once_with(run.id)


class WorkflowClaimBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_executors_only_review_claimed_run_once(self):
        context = ReviewContext(uuid4(), uuid4(), "key", "contract.docx")
        content = VersionContent(
            context.version_id,
            "真实合同条款",
            "hash",
            "python-docx",
        )

        class ClaimOnceRepository:
            def __init__(self):
                self._lock = asyncio.Lock()
                self._claimed = False
                self.completed = AsyncMock()
                self.failed = AsyncMock()

            async def claim_run(self, _run_id):
                async with self._lock:
                    if self._claimed:
                        return None
                    self._claimed = True
                    return context

            async def get_content(self, _version_id):
                return content

            async def mark_parsing(self, _context):
                raise AssertionError("cached content should skip parsing")

            async def save_content(self, _content):
                raise AssertionError("cached content should not be saved again")

            async def mark_analyzing(self, _context):
                return None

            async def complete_run(self, ctx, result):
                await self.completed(ctx, result)

            async def fail_run(self, run_id, message):
                await self.failed(run_id, message)

        repository = ClaimOnceRepository()
        reviewer = SimpleNamespace(
            review=AsyncMock(
                return_value=ContractAnalysis(document_type="合同", summary="摘要")
            )
        )
        parser = SimpleNamespace(parse=AsyncMock())
        workflow = ContractReviewWorkflow(_ServiceSession(), repository, parser, reviewer)

        await asyncio.gather(workflow.run(context.run_id), workflow.run(context.run_id))

        reviewer.review.assert_awaited_once()
        repository.completed.assert_awaited_once()
        repository.failed.assert_not_awaited()


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
        repository = SqlAlchemyContractReviewStore(session)
        repository.get_owned_version = AsyncMock(return_value=object())

        history = await repository.list_history(7, uuid4(), version_id)

        self.assertEqual([item.attempt for item in history], [2, 1])

    async def test_select_accepts_only_completed_run_for_same_version(self):
        version_id = uuid4()
        completed = self._run(version_id=version_id)
        session = _FakeSession(scalar_results=[completed])
        repository = SqlAlchemyContractReviewStore(session)
        repository.get_owned_version = AsyncMock(return_value=object())

        selected = await repository.select_run(
            7, uuid4(), version_id, completed.id
        )

        self.assertTrue(selected)
        session.execute.assert_awaited_once()
        session.commit.assert_not_awaited()

    async def test_select_rejects_other_version_or_unfinished_run(self):
        version_id = uuid4()
        for rejected in (None, None):
            with self.subTest(case=rejected):
                session = _FakeSession(scalar_results=[rejected])
                repository = SqlAlchemyContractReviewStore(session)
                repository.get_owned_version = AsyncMock(return_value=object())

                selected = await repository.select_run(
                    7, uuid4(), version_id, uuid4()
                )

                self.assertFalse(selected)
                session.execute.assert_not_awaited()
                session.commit.assert_not_awaited()

    async def test_user_cannot_read_or_select_unowned_version(self):
        session = _FakeSession()
        repository = SqlAlchemyContractReviewStore(session)
        repository.get_owned_version = AsyncMock(return_value=None)

        self.assertIsNone(await repository.load_snapshot(8, uuid4(), uuid4()))
        self.assertIsNone(await repository.list_history(8, uuid4(), uuid4()))
        self.assertFalse(
            await repository.select_run(8, uuid4(), uuid4(), uuid4())
        )
        session.scalar_results = []
        session.execute.assert_not_awaited()


class SchemaSafetyBehaviorTests(unittest.TestCase):
    def test_contract_schema_is_not_initialized_at_application_startup(self):
        import inspect

        from app import db as app_db

        source = inspect.getsource(app_db.init_db_tables)
        self.assertNotIn("CREATE UNIQUE INDEX", source)
        self.assertNotIn("_apply_contract_analysis_column_patches", source)
        self.assertIn("_legacy_tables", source)

    def test_version_model_declares_unique_contract_number_constraint(self):
        constraints = {
            constraint.name
            for constraint in ContractVersionModel.__table__.constraints
            if constraint.name
        }
        self.assertIn("uq_contract_version_number", constraints)


class VersionAllocationBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_version_api_uses_contract_lock_and_store_allocator(self):
        contract_id = uuid4()
        store = SimpleNamespace(
            lock_owned_contract=AsyncMock(return_value=object()),
            get_next_version_number=AsyncMock(return_value=3),
            create_version=AsyncMock(),
        )
        service = ContractVersionApplicationService(
            repository=SimpleNamespace(),
            contracts=SimpleNamespace(),
            session=_ServiceSession(),
            review_store=store,
        )

        version = await service.create(
            user_id=7,
            contract_id=contract_id,
            source_key="oss://contract/v3.pdf",
            filename="v3.pdf",
        )

        self.assertEqual(version.number, 3)
        store.lock_owned_contract.assert_awaited_once_with(7, contract_id)
        store.get_next_version_number.assert_awaited_once_with(contract_id)
        store.create_version.assert_awaited_once()


class JobDispatcherBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_fastapi_adapter_enqueues_analysis_handler(self):
        background_tasks = BackgroundTasks()
        dispatcher = FastApiBackgroundJobDispatcher(background_tasks)
        run_id = uuid4()

        await dispatcher.dispatch_analysis(run_id)

        self.assertEqual(len(background_tasks.tasks), 1)
        task = background_tasks.tasks[0]
        self.assertEqual(task.func.__name__, "execute_analysis")
        self.assertEqual(task.args, (run_id,))


if __name__ == "__main__":
    unittest.main()
