from app.chat.service import ChatService
import json
import traceback
from pathlib import Path


OUT = Path(__file__).resolve().parent / "phase_a_assert_result.json"


def flush(payload):
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def assert_true(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def run_case(s: ChatService, cid: str | None, question: str):
    r = s.chat(
        question=question,
        conversation_id=cid,
        model_id=None,
        use_rag=False,
        selected_doc_ids=None,
        owner="tester",
        course_id=None,
    )
    new_cid = r.get("conversation_id")
    meta = r.get("meta", {}) if isinstance(r, dict) else {}
    report = meta.get("report", {}) if isinstance(meta.get("report", {}), dict) else {}
    return new_cid, r, meta, report


def main():
    state = {"status": "RUNNING", "step": "init", "results": []}
    flush(state)

    s = ChatService()
    cid = None

    cases = [
        (1, "帮我写个西游记报告"),
        (2, "孙悟空人物形象"),
        (3, "按常规写"),
        (4, "别问了直接生成"),
    ]

    for case_id, q in cases:
        state["step"] = f"case_{case_id}_start"
        flush(state)

        cid, r, m, rep = run_case(s, cid, q)
        resp_type = m.get("response_type")

        if case_id == 1:
            assert_true(resp_type == "ask", "Case1 应该进入 ask")
        elif case_id == 2:
            assert_true(resp_type in {"ask", "outline"}, "Case2 response_type 异常")
        elif case_id == 3:
            assert_true(resp_type in {"ask", "outline"}, "Case3 response_type 异常")
        elif case_id == 4:
            assert_true(resp_type in {"outline", "generate"}, "Case4 应该放行到 outline/generate")

        state["results"].append(
            {
                "case": case_id,
                "question": q,
                "response_type": resp_type,
                "report": rep,
                "answer_preview": str(r.get("answer", ""))[:120],
            }
        )
        state["step"] = f"case_{case_id}_done"
        flush(state)

    state["status"] = "PASS"
    state["step"] = "done"
    flush(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        flush(
            {
                "status": "FAIL",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        raise
