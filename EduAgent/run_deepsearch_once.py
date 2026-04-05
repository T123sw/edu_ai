import json
import traceback

from deepsearch import deepsearch_large_llm


def main() -> None:
    query = "计算思维 课程大纲 PDF"
    out = {"query": query}
    try:
        out["result"] = deepsearch_large_llm(query)
    except Exception as e:
        out["error_type"] = type(e).__name__
        out["error"] = str(e)
        out["traceback"] = traceback.format_exc()

    with open("deepsearch_run_out.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("WROTE deepsearch_run_out.json")


if __name__ == "__main__":
    main()


