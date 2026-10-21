"""Derive evidence from observer copies; ffprobe only reads finished video files."""
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((OUT / name).read_text())


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))


latest = read("latest.json")
start = datetime.fromisoformat(latest["attempt_started_at"]).timestamp()
snapshots = [json.loads(line) for line in (OUT / "snapshots.jsonl").read_text().splitlines()]
peaks = {"resources": 0, "videos": 0, "scene_workers": 0}
for s in snapshots:
    running = [a for a in s["artifacts"] if a["status"] == "running"]
    peaks["resources"] = max(peaks["resources"], len(running))
    peaks["videos"] = max(peaks["videos"], sum(a["type"] == "classroom" for a in running))
    peaks["scene_workers"] = max(peaks["scene_workers"], sum(
        w["status"] == "running" for a in s["artifacts"] for w in a.get("scene_workers", [])))
workers = []
render_boundaries = []
for a in latest["artifacts"]:
    for w in a.get("scene_workers", []):
        workers.append({"node": a["node"], **w,
                        "queue_seconds": round(w["started_at"] - w["submitted_at"], 3) if w.get("started_at") else None,
                        "execution_seconds": round(w["finished_at"] - w["started_at"], 3) if w.get("finished_at") else None})
    if a["type"] == "classroom":
        events = read(a["id"] + "/host-events.json")
        for event in events:
            if event["tool"] != "render_project" or not event.get("command_id"):
                continue
            render_boundaries.append((event["at"], 1))
            end = next((e for e in events if e["tool"] == "poll_command"
                        and e.get("command_id") == event["command_id"]
                        and e.get("exit_code") is not None), None)
            if end:
                render_boundaries.append((end["at"], -1))
render_active = render_peak = 0
for _, change in sorted(render_boundaries):
    render_active += change
    render_peak = max(render_peak, render_active)
save("concurrency-observations.json", {
    "method": "30-second snapshots, supplemented by exact worker lifecycle timestamps; sampled peaks are lower bounds",
    "sample_count": len(snapshots), "sampled_peaks": peaks, "scene_workers": workers,
    "render_command_peak_including_admission_and_polling": render_peak})

probe = []
nonzero = []
transport = []
session_errors = []
for a in latest["artifacts"]:
    if a["type"] != "classroom":
        continue
    for session in (Path(a["workspace"]) / ".host/sessions").glob("*.jsonl"):
        for line in session.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if any(word in event.get("type", "").lower() for word in ("error", "retry", "timeout")):
                session_errors.append({"node": a["node"], "session": session.name, "event": event})
    for project in a.get("projects", []):
        for video in project.get("renders", []):
            if a["status"] != "draft":
                continue
            path = Path(project["path"]) / "renders" / video["name"]
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                capture_output=True, text=True, timeout=20)
            data = json.loads(result.stdout) if result.returncode == 0 else None
            probe.append({"node": a["node"], "path": str(path), "returncode": result.returncode,
                          "data": data, "error": result.stderr or None})
    events = read(a["id"] + "/host-events.json")
    seen = set()
    for event in events:
        if event.get("exit_code") not in (None, 0) and event.get("command_id") not in seen:
            seen.add(event.get("command_id"))
            log = OUT / a["id"] / "commands" / (event["command_id"] + ".log")
            nonzero.append({"node": a["node"], **event, "log": str(log.relative_to(OUT)),
                            "excerpt": log.read_text()[-3000:] if log.exists() else None})
    for log in (OUT / a["id"] / "commands").glob("*.log"):
        for line in log.read_text().splitlines():
            if re.search(r"HTTPStatusError|HTTP[^\n]{0,30}\b429\b|QueuePool|3o7r|ReadTimeout|ConnectTimeout", line):
                transport.append({"node": a["node"], "log": str(log.relative_to(OUT)), "line": line[:1000]})
save("media-probe.json", probe)
save("nonzero-commands.json", nonzero)
save("transport-errors.json", {"scope": "Copied native command logs only; model retries without logged exceptions are not excluded",
                              "matches": transport})
save("session-error-events.json", {
    "scope": "Structured session error/retry/timeout event types; model reasoning text excluded",
    "events": session_errors})
save("playback-checks.json", {"performed": False,
                             "reason": "Read-only observation: ffprobe metadata and existing native screenshots only; no interactive playback or re-render initiated."})
print(json.dumps({"counts": latest["resource_counts"], "peaks": peaks,
                  "probed_videos": len(probe), "nonzero_commands": len(nonzero),
                  "transport_matches": len(transport),
                  "model_retries": sum(x["event"]["type"] == "llm/retry" for x in session_errors)}, ensure_ascii=False))
