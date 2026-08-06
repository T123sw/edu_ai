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
