import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def preparation(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("source_preparation", ROOT / "scripts" / "prepare_upstream.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    module.git(upstream, "init", "--quiet")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "deeptutor/keep", "web/keep", "tests/keep"):
        file = upstream / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("original\n")
    module.git(upstream, "add", ".")
    module.git(upstream, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
    commit = module.git(upstream, "rev-parse", "HEAD").strip()
    (upstream / "deeptutor/keep").write_text("adapted\n")
    diff = module.git(upstream, "diff", "--binary", "--no-ext-diff", "--no-color")
    (upstream / "deeptutor/keep").write_text("original\n")
    lock_root = tmp_path / "lock"
    (lock_root / "patches").mkdir(parents=True)
    patch = lock_root / "patches" / "change.patch"
    patch.write_text(diff)
    (lock_root / "upstream.lock.json").write_text(json.dumps({
        "repository": str(upstream), "commit": commit, "version": "fixture",
        "patches": [{"file": patch.name, "sha256": hashlib.sha256(patch.read_bytes()).hexdigest()}]}))
    monkeypatch.setattr(module, "ROOT", lock_root)
    return module, tmp_path / "target"


def test_source_reproducible_and_idempotent_without_resetting_work(preparation):
    module, target = preparation
    first = module.prepare(target)
    assert module.prepare(target) == first
    assert (target / "deeptutor/keep").read_text() == "adapted\n"
    (target / "deeptutor/keep").write_text("developer work\n")
    with pytest.raises(RuntimeError, match="Local changes"):
        module.prepare(target)
    assert (target / "deeptutor/keep").read_text() == "developer work\n"


def test_tampered_patch_is_rejected_before_fetch(preparation):
    module, target = preparation
    (module.ROOT / "patches/change.patch").write_text("tampered")
    with pytest.raises(RuntimeError, match="checksum"):
        module.prepare(target)
    assert not target.exists()


def test_partial_fetch_can_resume(preparation):
    module, target = preparation
    target.mkdir()
    module.git(target, "init", "--quiet")
    repository = json.loads((module.ROOT / "upstream.lock.json").read_text())["repository"]
    module.git(target, "remote", "add", "origin", repository)
    module.prepare(target)
    assert (target / "deeptutor/keep").read_text() == "adapted\n"


def test_known_previous_patch_can_upgrade_without_accepting_unknown_edits(preparation):
    module, target = preparation
    module.prepare(target)
    path = module.ROOT / 'upstream.lock.json'
    lock = json.loads(path.read_text())
    lock['previous_patch_sets'] = [lock['patches']]
    (target / 'deeptutor/keep').write_text('next version\n')
    patch = module.ROOT / 'patches/next.patch'
    patch.write_text(module.git(target, 'diff', '--binary', '--no-ext-diff', '--no-color'))
    (target / 'deeptutor/keep').write_text('adapted\n')
    lock['patches'] = [{'file': patch.name, 'sha256': hashlib.sha256(patch.read_bytes()).hexdigest()}]
    path.write_text(json.dumps(lock))
    module.prepare(target)
    assert (target / 'deeptutor/keep').read_text() == 'next version\n'


def test_managed_added_modules_are_recorded_and_upgrade_reproducibly(preparation):
    module,target=preparation
    module.prepare(target)
    lock_path=module.ROOT/'upstream.lock.json';lock=json.loads(lock_path.read_text());lock['previous_patch_sets']=[lock['patches']]
    added=target/'deeptutor/new_module.py';added.write_text('VALUE = 42\n')
    module.git(target,'add','-N','deeptutor/new_module.py')
    patch=module.ROOT/'patches/added.patch';patch.write_text(module.git(target,'diff','--binary','--no-ext-diff','--no-color'))
    module.git(target,'reset','--','deeptutor/new_module.py');added.unlink()
    lock['patches']=[{'file':patch.name,'sha256':hashlib.sha256(patch.read_bytes()).hexdigest()}];lock_path.write_text(json.dumps(lock))
    module.prepare(target);assert added.read_text()=='VALUE = 42\n'
    assert not module.git(target,'diff','--cached','--name-only').strip()
    assert module.prepare(target)==module.prepare(target)
    fresh=target.parent/'fresh';module.prepare(fresh)
    assert (fresh/'deeptutor/new_module.py').read_text()=='VALUE = 42\n'
