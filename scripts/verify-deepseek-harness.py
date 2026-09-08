"""Live SDK + existing durable report pipeline smoke test in isolated storage.

Run with the backend environment. Reads configured model credentials, but uses
only synthetic users/courses and never writes to the application's databases.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend/src"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    from core.config import Config
    import dotenv
    # Some legacy RAG imports reload dotenv with override=True. Credentials
    # are already loaded; prohibit that reload inside this verification process.
    dotenv.load_dotenv = lambda *args, **kwargs: False
    # Config loads the project dotenv. Override only inside this smoke process,
    # before constructing persistence services; never modify the real dotenv.
    for key in ("USER", "JOB", "TASK", "MATERIAL", "COURSE", "COURSE_MEMBERSHIP", "KNOWLEDGE", "APP_STATE", "CONVERSATION", "LEARNING"):
        os.environ[key + "_PERSISTENCE_MODE"] = "json"
    os.environ["DATABASE_URL"] = ""
    os.environ["TASKS_DB_PATH"] = str(output / "tasks.sqlite")
    os.environ["COURSE_STORAGE_ROOT"] = str(output / "courses")
    Config.STORAGE_ROOT = output / "storage"
    Config.COURSE_STORAGE_ROOT = output / "courses"
    Config.RUNTIME_CONFIG_ROOT = output / "runtime_config"

    from app.chat.domain.contracts import ChatRequestV2
    from app.chat.domain.conversation_snapshot import ConversationSnapshot
    from app.chat.harness.runtime import HarnessRuntime
    from app.chat.harness.store import HarnessStore
    from app.chat.harness.tools import ReportTools
    from app.chat.harness.content_gateway import build_content_gateway
    from app.chat.tasks.task_store import TaskStore
    from app.services.generation_command import GenerationCommandService
    from app.services.generation_task_handlers import GenerationTaskHandler
    from app.services.durable_task_handlers import DurableTaskHandlerRegistry
    from app.services.durable_task_executor import DurableTaskExecutor
    from app.services.job_completion_service import JobCompletionService
    from app.services.job_store import get_job, cancel_job
    from core.course_storage import CourseStorageManager

    tasks = TaskStore(db_path=str(output / "tasks.sqlite"))
    assert not os.environ.get("DATABASE_URL")
    assert os.environ["JOB_PERSISTENCE_MODE"] == os.environ["MATERIAL_PERSISTENCE_MODE"] == "json"
    manager = CourseStorageManager(root_path=str(output / "courses"))
    commands = GenerationCommandService(task_store=tasks, snapshot_provider=lambda owner: {})
    registry = DurableTaskHandlerRegistry()
    registry.register("report_direct", 1, GenerationTaskHandler(course_storage_manager=manager))
    executor = DurableTaskExecutor(task_store=tasks, handler_registry=registry,
                                  completion_service=JobCompletionService(task_store=tasks, course_storage_manager=manager))

    def read_artifact(ref, owner):
        return manager.get_generated_material(ref["course_id"], ref["material_type"], ref["material_id"], owner_user_id=owner)

    def tool_factory(**kwargs):
        return ReportTools(**kwargs, gateway=build_content_gateway(), submit=commands.submit,
                           get_job=get_job, read_artifact=read_artifact, cancel_job=cancel_job,
                           validate_scope=lambda request: None)

    def runtime():
        return HarnessRuntime(store=HarnessStore(output / "sessions"), tool_factory=tool_factory,
                              model=Config.DSH_MODEL, api_key=Config.DEEPSEEK_API_KEY,
                              base_url=Config.DEEPSEEK_BASE_URL, timeout=300)

    results = []
    def turn(question, index):
        start = time.monotonic()
        request = ChatRequestV2(question=question, request_id=f"smoke-{index}",
                               owner="harness-smoke", course_id="harness-smoke-course", conversation_id="smoke-conversation")
        events = list(runtime().run_stream(request=request, snapshot=ConversationSnapshot()))
        result = next(e["payload"] for e in reversed(events) if e["type"] == "result")
        record = {"turn": index, "seconds": round(time.monotonic()-start, 2),
                  "event_types": [e["type"] for e in events], "result": result}
        results.append(record)
        (output / "smoke.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(json.dumps({"turn": index, "seconds": record["seconds"], "action": result["action"],
                          "tools": [e["tool"] for e in result["trace"].get("tool_events", [])]}, ensure_ascii=False), flush=True)
        assert result["action"]["name"] != "agent.failed", result["trace"]
        return result

    first = turn("请用一句话解释递归的终止条件，不要生成任何资料。", 1)
    assert not first["trace"]["tool_events"]
    second = turn("我上一条问的是什么？简短回答。", 2)
    assert "递归" in second["message"]["content"]
    outline = turn("请生成《递归终止条件：基线可达性与规模递减》教学报告，受众为学过 Python 函数的初学者。先只给大纲，恰好三章，全文约800字，不联网、不检索资料。聚焦终止条件，使用非负整数阶乘和倒计时作为示例，写明输入域；检查基线可达性、严格递减及其下界，不扩展到二分查找、树、链表或性能优化。", 3)
    assert outline.get("harness_outline")
    assert all(e["tool"] != "submit_report" for e in outline["trace"]["tool_events"])
    submitted = turn("确认大纲并继续", 4)
    job_id = submitted["task_id"]
    assert get_job(job_id).status.value == "queued"
    print("执行已有 durable 报告任务服务…", flush=True)
    assert executor.run_once()
    job = get_job(job_id)
    print("生成任务状态：" + job.status.value, flush=True)
    assert job.status.value == "succeeded", {"status": job.status.value, "error_code": job.error_code}
    assert (Config.STORAGE_ROOT / "jobs" / (job_id + ".json")).is_file()
    assert list((output / "courses").rglob("*.json")), "Report must be saved in the isolated file store"
    final = turn("查看刚才报告的生成结果，读取并检查产物。", 5)
    assert final.get("artifacts")
    assert final["verification"]["decision"] == "pass"
    assert final["verification"]["semantic_review"] == "model_review"
    (output / "report.md").write_text(final["artifacts"][0]["content"])
    (output / "review.json").write_text(json.dumps(final["verification"]["review"], ensure_ascii=False, indent=2))
    assert read_artifact(job.result_ref, "harness-smoke")["content"] == final["artifacts"][0]["content"]
    (output / "verification.json").write_text(json.dumps({"passed": True, "turns": 5,
        "live_sdk": True, "live_outline_model": True, "real_durable_report_pipeline": True,
        "storage": "isolated", "report_characters": len(final["artifacts"][0]["content"])}, indent=2))


if __name__ == "__main__":
    main()
