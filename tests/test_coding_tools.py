import pytest

from horde.builtin_tools import edit_file, list_files, search_files


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def hello():\n    return 'hi'\n")
    (tmp_path / "notes.md").write_text("hello world\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("hello from git\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_edit_file_replaces_exactly_one_occurrence(project):
    assert edit_file.function("src/app.py", "'hi'", "'hello'") == "Edited src/app.py"
    assert (project / "src" / "app.py").read_text() == "def hello():\n    return 'hello'\n"


def test_edit_file_refuses_missing_or_ambiguous_text(project):
    (project / "twice.txt").write_text("a a")
    with pytest.raises(ValueError, match="found 0 times"):
        edit_file.function("src/app.py", "nope", "x")
    with pytest.raises(ValueError, match="found 2 times"):
        edit_file.function("twice.txt", "a", "b")
    assert (project / "twice.txt").read_text() == "a a"


def test_edit_file_needs_approval():
    assert edit_file.requires_approval({"path": "x", "old_text": "", "new_text": ""})


def test_list_files_skips_noise(project):
    assert list_files.function() == "notes.md\nsrc/app.py"
    assert list_files.function("**/*.py") == "src/app.py"
    assert list_files.function("**/*.rs") == "No files found"


def test_search_files_finds_lines(project):
    assert search_files.function("hello") == "notes.md:1: hello world\nsrc/app.py:1: def hello():"
    assert search_files.function("hello", pattern="**/*.md") == "notes.md:1: hello world"
    assert search_files.function("zzz") == "No matches"


def test_read_only_tools_ask_only_outside_workspace(project):
    assert not search_files.requires_approval({"regex": "x"})
    assert search_files.requires_approval({"regex": "x", "path": "/etc"})
    assert list_files.requires_approval({"path": ".."})
