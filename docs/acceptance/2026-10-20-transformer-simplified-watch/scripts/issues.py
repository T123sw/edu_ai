"""Classify saved observations, without changing production or running reviews."""
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]


def read(name, default=None):
    path = OUT / name
    return json.loads(path.read_text()) if path.exists() else default


state = read("latest.json")
audit = read("action-audit.json", {})
live = read("live-session-audit.json", {})
checks = []
for artifact in state["artifacts"]:
    if artifact["type"] != "classroom":
        continue
    check = read(artifact["id"] + "/native-check.json", {})
    sections = {
        key: {
            "ok": value.get("ok"),
            "errors": value.get("errorCount"),
            "warnings": value.get("warningCount"),
            "finding_codes": dict(Counter(f["code"] for f in value.get("findings", []))),
        }
        for key, value in check.items()
        if isinstance(value, dict) and "findings" in value
    }
    checks.append({"node": artifact["node"], "native_ok": check.get("ok"), "sections": sections})

commands = {}
for result in live.get("tool_results", []):
    if result["result"]["exit_code"] not in (None, 0):
        commands[result["result"]["command_id"]] = result

data = {
    "as_of": state["at"],
    "resource_failures": [
        {"id": a["id"], "node": a["node"], "type": a["type"], "error": a["error"]}
        for a in state["artifacts"] if a["status"] == "failed"
    ],
    "protocol_recoveries": audit.get("protocol_recoveries", []),
    "session_errors": live.get("session_errors", []),
    "native_tool_failures": [
        r for r in live.get("tool_results", []) if r["result"]["ok"] is False
    ],
    "nonzero_command_count": len(commands),
    "nonzero_command_detail": "nonzero-commands.json",
    "transport_log_scan": read("transport-errors.json"),
    "recovered_browser_check": {
        "node": "n3-positional-encoding",
        "failed_command": "2ca94ded56de47969d2173f85b6cd515",
        "message": "Native browser check incomplete; no successful receipt saved",
        "successful_followup_command": "eb8bde5240234d0685959f997a5f5b11",
        "followup_exit_code": 0,
        "status": "recovered_by_generator",
    },
    "other_command_errors": [
        "Exploratory reads/listings used nonexistent reference files or not-yet-created scene directories.",
        "One environment probe used the unavailable 'which' command (exit 127).",
    ],
    "narration_repetition": {
        "node": "n4-encoder", "prepare_narration_calls": 2,
        "initial_audio_seconds": 245.832, "later_audio_seconds": 291.936,
        "note": "Repeated narration preparation after content changes; not evidence of HTTP throttling.",
    },
    "layout_and_runtime_checks": checks,
    "check_interpretation": (
        "Native lint/runtime/layout findings are retained separately from the playback-first "
        "release decision. Native ok=false does not mean resource generation failed. "
        "Layout/contrast findings were advisory under the existing release policy; "
        "some refer to decorative ghost text. No claim that every finding is a visible defect "
        "or that every finished frame has been visually verified."
    ),
    "visual_spotcheck": read("visual-spotcheck.json"),
    "limitations": [
        "No semantic/numerical content review, extra model call, re-render, or interactive playback.",
        "A successful generation status does not establish all educational content is correct.",
        "Concurrency peaks use 30-second sampling and are lower bounds.",
    ],
}
(OUT / "observed-issues.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
print(json.dumps({
    "resource_failures": len(data["resource_failures"]),
    "protocol_recoveries": len(data["protocol_recoveries"]),
    "session_errors": len(data["session_errors"]),
    "nonzero_commands": len(commands),
}))
