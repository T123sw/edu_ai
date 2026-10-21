"""Publish only the reviewed frontend snapshot, preserving concurrent releases."""
import hashlib
import json
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
baseline = json.loads((root / "docs/acceptance/2026-10-20-explore-cleanup/release.json").read_text())
source = Path("/tmp/edu-video-chat-source-v2")
release = Path("/tmp/edu-video-chat-release-v2")
live = root / "frontend/dist"
changed = [
    "src/classroom/playbackTypes.ts",
    "src/selfLearning/Classroom.tsx",
    "src/selfLearning/Content.tsx",
    "src/liveLearning/MaterialEntry.tsx",
    "src/hyperframes/HyperframesClassroom.tsx",
    "src/stitch/course/classroomCatalog/ClassroomPlaybackSurface.tsx",
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert sha(live / "index.html") == baseline["releaseIndexSha256"], "A newer release must be incorporated first"
assert "3 passed" in (evidence / "release-tests.txt").read_text()
for name in changed:
    assert sha(root / "frontend" / name) == sha(source / "frontend" / name), f"Source changed: {name}"
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = root / "frontend/dist-release-backups" / f"before-video-chat-{stamp}"
shutil.copytree(live, backup)
assets = {str(p.relative_to(release)): sha(p) for p in release.rglob("*") if p.is_file()}
for name in assets:
    if name == "index.html":
        continue
    dest = live / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(release / name, dest)
assert sha(live / "index.html") == baseline["releaseIndexSha256"], "Concurrent deployment detected"
entry = live / ".index-video-chat.html"
shutil.copy2(release / "index.html", entry)
entry.replace(live / "index.html")
assert all(sha(live / name) == value for name, value in assets.items())
with urllib.request.urlopen("http://127.0.0.1/") as response:
    assert hashlib.sha256(response.read()).hexdigest() == assets["index.html"]
result = {
    "status": "published",
    "publishedAt": stamp,
    "baselineSource": baseline["sourceSnapshot"],
    "sourceSnapshot": str(source),
    "release": str(release),
    "previousIndexSha256": baseline["releaseIndexSha256"],
    "releaseIndexSha256": assets["index.html"],
    "backup": str(backup),
    "sourceManifest": {"frontend/" + name: sha(source / "frontend" / name) for name in changed},
    "assetManifest": assets,
    "nginxIndexMatches": True,
    "backendChanges": False,
    "businessDataWritten": False,
}
(evidence / "release.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({"published": True, "assets": len(assets), "backup": str(backup)}))
