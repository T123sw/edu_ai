"""Run the versioned offline teacher-Agent structural evaluation dataset."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from app.chat.evals.dataset import load_eval_dataset
    from app.chat.evals.evaluators import summarize_results
    from app.chat.evals.runner import run_offline_cases
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.chat.evals.dataset import load_eval_dataset
    from app.chat.evals.evaluators import summarize_results
    from app.chat.evals.runner import run_offline_cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "evals" / "teacher_agent" / "cases.yaml",
    )
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--fail-under", type=float, default=0.0)
    args = parser.parse_args()

    dataset = load_eval_dataset(args.dataset)
    cases = dataset.expand_cases()
    results = run_offline_cases(cases, repeat=args.repeat)
    summary = summarize_results(results)
    payload = {
        "schema_version": dataset.schema_version,
        "dataset_id": dataset.dataset_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repeat": args.repeat,
        "summary": summary.model_dump(mode="json"),
        "results": [result.model_dump(mode="json") for result in results],
    }

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(_markdown_report(payload), encoding="utf-8")

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 1 if summary.pass_rate < args.fail_under else 0


def _markdown_report(payload: dict) -> str:
    summary = payload["summary"]
    lines = [
        f"# Teacher Agent Eval — {payload['dataset_id']}",
        "",
        f"- Schema: `{payload['schema_version']}`",
        f"- Generated: `{payload['generated_at']}`",
        f"- Repeats: {payload['repeat']}",
        f"- Pass rate: {summary['pass_rate']:.2%}",
        f"- Mean structural score: {summary['mean_score']:.2%}",
        f"- P50/P95: {summary['p50_ms']:.2f} / {summary['p95_ms']:.2f} ms",
        "",
        "## Failure clusters",
        "",
        "| Code | Count |",
        "|---|---:|",
    ]
    clusters = summary["failure_clusters"]
    if clusters:
        lines.extend(f"| `{code}` | {count} |" for code, count in clusters.items())
    else:
        lines.append("| _none_ | 0 |")
    lines.extend(["", "## Failed runs", "", "| Case | Run | Score | Failures |", "|---|---:|---:|---|"])
    failed = [result for result in payload["results"] if not result["passed"]]
    if failed:
        for result in failed:
            codes = ", ".join(failure["code"] for failure in result["failures"])
            lines.append(
                f"| `{result['case_id']}` | {result['run_index']} | "
                f"{result['score']:.2%} | {codes} |"
            )
    else:
        lines.append("| _none_ | - | 100% | - |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
