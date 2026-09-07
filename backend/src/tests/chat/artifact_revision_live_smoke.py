"""Run explicitly; only temporary owned artifacts, no production course writes."""
import json
import os
import tempfile
from pathlib import Path
from app.chat.agents.report_generation import get_fallback_llm
from app.artifact_revision.service import ArtifactRevisionService
from core.course_storage import CourseStorageManager


def main():
    llm = get_fallback_llm()
    if llm is None:
        print(json.dumps({"status": "unavailable"}))
        return
    os.environ["MATERIAL_PERSISTENCE_MODE"] = "json"
    with tempfile.TemporaryDirectory(prefix="revision-live-") as directory:
        manager = CourseStorageManager(directory)
        service = ArtifactRevisionService(manager, llm)
        cases = [
            ("report", "# 数组基础\n\n## 定义\n数组按顺序存放同类型元素。\n\n## 案例\n使用数组保存成绩。\n\n## 独特证据\n保留标记：C-REVISION-20260907。", "仅在案例部分增加两个简短实际案例，保留其余内容。"),
            ("quiz", {"questions": [{"id": "q1", "stem": "数组下标通常从哪个数字开始？", "options": ["0", "1"], "answer": "A", "explanation": "在 Python 中，数组式序列的下标从0开始。"}]}, "只将题干改为明确询问Python列表的首个下标，保留选项、答案和解析。"),
        ]
        for kind, content, question in cases:
            manager.save_generated_material("c-revision-smoke", kind, kind, {"title": "数组测试资料", "content": content}, owner_user_id="c-revision-test", visibility="private")
            result = service.run(owner_user_id="c-revision-test", conversation_id="smoke", course_id="c-revision-smoke", question=question, operation_id=kind, artifact_reference={"artifact_id": kind, "artifact_type": kind, "version_id": "v1", "source_course_id": "c-revision-smoke"})
            print(json.dumps({"type": kind, "status": result["status"], "message": result.get("message"), "version": result.get("artifact_reference", {}).get("version_id"), "changes": result.get("changes"), "preserved_marker": "C-REVISION-20260907" in str(result.get("artifact", {}).get("content")) if kind == "report" else None}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
