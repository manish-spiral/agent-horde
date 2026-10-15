from horde import cli
from horde.loop import SYSTEM_PROMPT, new_conversation
from test_loop import FakeModel, answer


def test_instructions_extend_the_system_prompt():
    assert new_conversation()[0]["content"] == SYSTEM_PROMPT
    prompt = new_conversation("  Always answer in French.\n")[0]["content"]
    assert prompt.startswith(SYSTEM_PROMPT)
    assert prompt.endswith("Project instructions:\nAlways answer in French.")


def test_cli_reads_agents_md(tmp_path, monkeypatch):
    (tmp_path / "AGENTS.md").write_text("Use tabs, not spaces.")
    monkeypatch.chdir(tmp_path)
    fake = FakeModel([answer("ok")])
    monkeypatch.setattr(cli, "create_model", lambda *args: fake)
    monkeypatch.setattr("sys.argv", ["horde", "task"])

    assert cli.main() == 0
    assert "Use tabs, not spaces." in fake.received[0][0]["content"]


def test_no_instruction_file_means_default_prompt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.project_instructions() is None
