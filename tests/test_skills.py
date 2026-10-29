import pytest

from horde import cli
from horde.skills import load_skills, make_save_skill_tool, make_skill_tool, skills_summary
from test_loop import FakeModel, answer, tool_call


@pytest.fixture
def skills_dir(tmp_path):
    folder = tmp_path / "myskills"
    folder.mkdir()
    (folder / "release.md").write_text("\n# Cut a release: bump version, tag, push\n\n1. Edit pyproject\n")
    (folder / "review.md").write_text("Review code for bugs\nCheck tests first.")
    return folder


def test_skills_are_listed_by_summary(skills_dir):
    skills = load_skills(skills_dir)
    assert list(skills) == ["release", "review"]
    assert skills_summary(skills).splitlines()[1:] == [
        "- release: Cut a release: bump version, tag, push",
        "- review: Review code for bugs"]


def test_use_skill_returns_full_text(skills_dir):
    use_skill = make_skill_tool(load_skills(skills_dir))
    assert "1. Edit pyproject" in use_skill.function("release")
    with pytest.raises(ValueError, match="no skill 'x'; available: release, review"):
        use_skill.function("x")


def test_cli_lists_skills_and_offers_use_skill(skills_dir, monkeypatch):
    fake = FakeModel([tool_call("use_skill", {"name": "review"}), answer("done")])
    monkeypatch.setattr(cli, "create_model", lambda *args: fake)
    monkeypatch.setattr("sys.argv", ["horde", "--skills-dir", str(skills_dir), "task"])
    assert cli.main() == 0
    assert "- review: Review code for bugs" in fake.received[0][0]["content"]
    assert fake.received[1][-1]["content"] == "Review code for bugs\nCheck tests first."


def test_no_skills_folder_means_no_tool(tmp_path):
    assert load_skills(tmp_path / "none") == {}


def test_save_skill_writes_a_reusable_skill(tmp_path):
    skills = {}
    save_skill = make_save_skill_tool(tmp_path / "skills", skills)
    assert save_skill.requires_approval({})
    assert save_skill.function("deploy-docs", "Deploy the docs site\n1. run make\n") == \
        "Saved skill 'deploy-docs'."
    assert load_skills(tmp_path / "skills") == {"deploy-docs": "Deploy the docs site\n1. run make\n"}
    assert "deploy-docs" in skills


@pytest.mark.parametrize("name", ["Bad Name", "../escape", "", "x" * 70])
def test_save_skill_rejects_unsafe_names(tmp_path, name):
    with pytest.raises(ValueError, match="lowercase"):
        make_save_skill_tool(tmp_path, {}).function(name, "text")
