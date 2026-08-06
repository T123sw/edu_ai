from app.chat.tasks.task_store import TaskStore
from app.services.durable_job_runtime import (
    DurableJobRuntime,
    build_durable_job_runtime,
)


class FakeExecutor:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self, *, timeout_seconds: float = 10):
        assert timeout_seconds == 3
        self.stopped += 1
        return ()


class FakeReconciler:
    def __init__(self) -> None:
        self.calls = 0

    def reconcile_startup(self) -> None:
        self.calls += 1


def test_runtime_reconciles_before_starting_and_stops_idempotently(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))
    executor = FakeExecutor()
    reconciler = FakeReconciler()
    runtime = DurableJobRuntime(
        task_store=store,
        executor=executor,
        reconciler=reconciler,
    )

    runtime.start()
    runtime.start()
    runtime.stop(grace_seconds=3)
    runtime.stop(grace_seconds=3)

    assert reconciler.calls == 1
    assert executor.started == 1
    assert executor.stopped == 1
    store.close()


def test_default_runtime_registers_all_generation_workflows(tmp_path):
    store = TaskStore(str(tmp_path / "tasks.db"))

    runtime = build_durable_job_runtime(task_store=store)

    for workflow in (
        "report_direct",
        "lesson_plan_direct",
        "blog_direct",
        "quiz_direct",
        "ppt_direct",
        "flashcard_direct",
        "graph_direct",
        "game_direct",
    ):
        assert runtime.handler_registry.resolve(workflow, 1) is not None
    assert runtime.executor.worker_count >= 1
    store.close()
