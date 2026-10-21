"""Materialize the complete pinned upstream and apply the reviewed patch set.

Never resets an existing checkout or drops upstream modules. Local changes must
match the exact managed patch before an existing installation can be reused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(directory: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(directory), *args], text=True)


def apply_patch_set(target: Path, patches: list[Path]) -> None:
    # git 2.34 --intent-to-add can discard existing index entries during apply.
    # Apply first, then mark only newly added paths named by this patch set.
    # Existing untracked work is never added, staged or overwritten.
    names = []
    for entry in git(target, 'apply', '--numstat', '-z', *(str(p) for p in patches)).split('\0'):
        fields = entry.split('\t', 2)
        if len(fields) == 3 and fields[2]: names.append(fields[2])
    git(target, 'apply', *(str(p) for p in patches))
    untracked = set(git(target, 'ls-files', '--others', '--exclude-standard', '-z').split('\0'))
    added = [name for name in names if name in untracked]
    if added: git(target, 'add', '-N', '--', *added)


def prepare(target: Path) -> dict:
    lock = json.loads((ROOT / "upstream.lock.json").read_text())
    patches = []
    for entry in lock["patches"]:
        path = ROOT / "patches" / entry["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"Patch checksum mismatch: {path.name}")
        patches.append(path)
    if not (target / ".git").exists():
        if target.exists() and any(target.iterdir()):
            raise RuntimeError("Refusing to overwrite a nonempty source directory")
        target.mkdir(parents=True, exist_ok=True)
        git(target, "init", "--quiet")
        git(target, "remote", "add", "origin", lock["repository"])
    head = subprocess.run(["git", "-C", str(target), "rev-parse", "--verify", "HEAD"], capture_output=True, text=True)
    if head.returncode:
        if git(target, "remote", "get-url", "origin").strip() != lock["repository"]:
            raise RuntimeError("Unexpected source remote in incomplete checkout")
        # Full snapshot, including tests, frontend, assets and license notices.
        git(target, "fetch", "--depth=1", "origin", lock["commit"])
        git(target, "checkout", "--detach", lock["commit"])
    if git(target, "rev-parse", "HEAD").strip() != lock["commit"]:
        raise RuntimeError("Unexpected upstream revision; use a fresh target directory")
    if git(target, "diff", "--cached", "--name-only").strip():
        raise RuntimeError("Refusing to modify a checkout containing staged changes")
    expected = "".join(path.read_text() for path in patches)
    current = git(target, "diff", "--binary", "--no-ext-diff", "--no-color")
    if current and current != expected:
        previous = None
        for entries in lock.get("previous_patch_sets", []):
            paths = [ROOT / "patches" / entry["file"] for entry in entries]
            if any(hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
                   for path, entry in zip(paths, entries)):
                raise RuntimeError("Previous patch checksum mismatch")
            if current == "".join(path.read_text() for path in paths):
                previous = paths
                break
        if previous is None:
            raise RuntimeError("Local changes differ from the managed patch; refusing to overwrite")
        git(target, "apply", "--reverse", *(str(path) for path in reversed(previous)))
        try:
            git(target, "apply", "--check", *(str(path) for path in patches))
            apply_patch_set(target, patches)
        except Exception:
            apply_patch_set(target, previous)
            raise
        current = expected
    if not current and patches:
        git(target, "apply", "--check", *(str(path) for path in patches))
        apply_patch_set(target, patches)
    actual = git(target, "diff", "--binary", "--no-ext-diff", "--no-color")
    if actual != expected:
        raise RuntimeError("Applied diff does not match the pinned patch")
    for required in ("LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "deeptutor", "web", "tests"):
        if not (target / required).exists():
            raise RuntimeError(f"Incomplete source snapshot: {required}")
    return {"commit": lock["commit"], "version": lock["version"], "source": str(target), "patches": lock["patches"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=ROOT / ".upstream" / "DeepTutor")
    args = parser.parse_args()
    print(json.dumps(prepare(args.target.resolve()), indent=2))
