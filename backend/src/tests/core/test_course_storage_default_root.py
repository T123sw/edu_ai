from pathlib import Path

from core.course_storage import _default_course_storage_root


def test_default_storage_uses_primary_checkout_for_linked_git_worktree(tmp_path: Path):
    primary_checkout = tmp_path / "edu_ai"
    common_git_dir = primary_checkout / ".git"
    linked_git_dir = common_git_dir / "worktrees" / "feature"
    linked_git_dir.mkdir(parents=True)
    (linked_git_dir / "commondir").write_text("../..\n", encoding="utf-8")

    linked_checkout = tmp_path / "feature"
    linked_checkout.mkdir()
    (linked_checkout / ".git").write_text(
        f"gitdir: {linked_git_dir.as_posix()}\n",
        encoding="utf-8",
    )
    module_path = linked_checkout / "Edu_AI" / "api" / "src" / "core" / "course_storage.py"

    assert _default_course_storage_root(module_path) == (
        primary_checkout / "Edu_AI" / "api" / "course_data"
    )


def test_default_storage_keeps_local_api_root_outside_git(tmp_path: Path):
    module_path = tmp_path / "app" / "api" / "src" / "core" / "course_storage.py"

    assert _default_course_storage_root(module_path) == tmp_path / "app" / "api" / "course_data"
