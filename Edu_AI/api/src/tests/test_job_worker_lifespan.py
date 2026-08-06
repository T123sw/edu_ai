from fastapi.testclient import TestClient


class FakeRuntime:
    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self, *, grace_seconds: float = 10) -> None:
        assert grace_seconds == 10
        self.stopped += 1


class FakeMembershipBootstrap:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.sync_calls = 0

    def sync_existing(self):
        self.sync_calls += 1
        self.events.append("memberships")


def test_app_lifespan_starts_and_stops_one_runtime():
    from app.bootstrap import create_app

    runtime = FakeRuntime()
    app = create_app(durable_runtime_factory=lambda: runtime)

    with TestClient(app):
        assert runtime.started == 1
        assert app.state.durable_job_runtime is runtime

    assert runtime.stopped == 1


def test_each_app_build_gets_an_independent_runtime():
    from app.bootstrap import create_app

    runtimes: list[FakeRuntime] = []

    def factory() -> FakeRuntime:
        runtime = FakeRuntime()
        runtimes.append(runtime)
        return runtime

    first = create_app(durable_runtime_factory=factory)
    second = create_app(durable_runtime_factory=factory)

    with TestClient(first), TestClient(second):
        assert len(runtimes) == 2
        assert runtimes[0] is not runtimes[1]
        assert [runtime.started for runtime in runtimes] == [1, 1]

    assert [runtime.stopped for runtime in runtimes] == [1, 1]


def test_memberships_are_backfilled_before_workers_start():
    from app.bootstrap import create_app

    events: list[str] = []
    membership_bootstrap = FakeMembershipBootstrap(events)

    class OrderedRuntime(FakeRuntime):
        def start(self) -> None:
            events.append("runtime")
            super().start()

    runtime = OrderedRuntime()
    app = create_app(
        durable_runtime_factory=lambda: runtime,
        membership_bootstrap_factory=lambda: membership_bootstrap,
    )

    with TestClient(app):
        assert events == ["memberships", "runtime"]
        assert membership_bootstrap.sync_calls == 1
