"""Run focused integration regressions without accessing configured databases."""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend/src"))


def main():
    from core.config import Config
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: False
    with tempfile.TemporaryDirectory(prefix="edu-harness-tests-") as directory:
        root = Path(directory)
        for key in ("USER", "JOB", "TASK", "MATERIAL", "COURSE", "COURSE_MEMBERSHIP",
                    "KNOWLEDGE", "APP_STATE", "CONVERSATION", "LEARNING"):
            os.environ[key + "_PERSISTENCE_MODE"] = "json"
        os.environ["DATABASE_URL"] = ""
        os.environ["TASKS_DB_PATH"] = str(root / "tasks.sqlite")
        os.environ["COURSE_STORAGE_ROOT"] = str(root / "courses")
        for name in ("STORAGE_ROOT", "COURSE_STORAGE_ROOT", "CONVERSATIONS_FILE", "COURSE_MEMBERSHIPS_FILE",
                     "USER_PROFILES_FILE", "LESSON_PLANS_FILE", "LEARNING_DB_PATH", "RUNTIME_CONFIG_ROOT"):
            old = getattr(Config, name)
            value = root / name.lower() if name.endswith("ROOT") else root / Path(old).name
            setattr(Config, name, value)
            os.environ[name] = str(value)
        Config.USE_DEEPSEEK_HARNESS = False  # Tests inject the pilot explicitly.
        files = ["test_knowledge_context_clarification.py", "test_reviewed_report.py", "test_harness_runtime.py", "test_main_orchestrator_stream.py", "test_reply_service_v2.py",
                 "test_reply_service_v2_stream.py", "test_schemas_v2.py", "test_schemas_v2_api.py",
                 "test_routes_v2_stream.py", "test_course_scope_routes.py"]
        os.chdir(root)
        import pytest
        return pytest.main(["-q", *[str(REPO / "backend/src/tests/chat" / file) for file in files]])


if __name__ == "__main__":
    raise SystemExit(main())
