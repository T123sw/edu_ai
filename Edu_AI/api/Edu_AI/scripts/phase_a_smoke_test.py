import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.chat.service import ChatService


def run():
    s = ChatService()
    cid = None
    cases = [
        "帮我写个西游记报告",
        "孙悟空人物形象",
        "按常规写",
        "别问了直接生成",
    ]
    for i, q in enumerate(cases, 1):
        r = s.chat(
            question=q,
            conversation_id=cid,
            model_id=None,
            use_rag=False,
            selected_doc_ids=None,
            owner="tester",
            course_id=None,
        )
        cid = r.get("conversation_id")
        meta = r.get("meta", {}) if isinstance(r, dict) else {}
        report_state = meta.get("report_state", {}) if isinstance(meta.get("report_state", {}), dict) else {}
        print(f"\n--- case {i} ---")
        print("q:", q)
        print("response_type:", meta.get("response_type"))
        print("missing:", report_state.get("missing"))
        print("ask_counts:", report_state.get("ask_counts"))
        print("soft_params_confirmed:", report_state.get("soft_params_confirmed"))
        print("answer:", str(r.get("answer", ""))[:180])


if __name__ == "__main__":
    run()
