import pytest

from horde import cli
from horde.loop import new_conversation, run_agent
from horde.session import load_session, save_session
from test_loop import FakeModel, answer


def test_save_and_load_session(tmp_path):
    save_session(tmp_path, "2026-01-01", [{"role": "user", "content": "old"}])
    save_session(tmp_path, "2026-01-02", [{"role": "user", "content": "new"}])

    assert load_session(tmp_path, "2026-01-01") == ("2026-01-01", [{"role": "user", "content": "old"}])
    assert load_session(tmp_path, "last")[0] == "2026-01-02"
    with pytest.raises(RuntimeError, match="no session 'nope'"):
        load_session(tmp_path, "nope")
    with pytest.raises(RuntimeError, match="no saved sessions"):
        load_session(tmp_path / "empty", "last")


def test_run_agent_continues_a_conversation():
    messages = new_conversation()
    model = FakeModel([answer("Hi Manish"), answer("Your name is Manish")])

    run_agent("my name is Manish", model, [], messages=messages)
    assert run_agent("what is my name?", model, [], messages=messages) == "Your name is Manish"

    second_request = model.received[1]
    assert [m["role"] for m in second_request] == ["system", "user", "assistant", "user"]
    assert second_request[2]["content"] == "Hi Manish"


def fake_cli(monkeypatch, replies, argv, typed=()):
    fake = FakeModel(replies)
    monkeypatch.setattr(cli, "create_model", lambda *args: fake)
    monkeypatch.setattr("sys.argv", ["horde", *argv])
    lines = list(typed)

    def fake_input():
        if not lines:
            raise EOFError
        return lines.pop(0)
    monkeypatch.setattr("builtins.input", fake_input)
    return fake


def test_chat_mode_keeps_context_between_turns(monkeypatch, capsys, private_session_dir):
    fake = fake_cli(monkeypatch, [answer("noted"), answer("blue")], [],
                    typed=["my favourite colour is blue", "", "which colour?", "exit"])

    assert cli.main() == 0
    assert capsys.readouterr().out.split() == ["noted", "blue"]
    assert "my favourite colour is blue" in str(fake.received[1])
    [session_file] = private_session_dir.glob("*.json")
    assert "which colour?" in session_file.read_text()


def test_resume_continues_a_saved_session(monkeypatch, private_session_dir):
    fake_cli(monkeypatch, [answer("first")], ["remember 42"])
    assert cli.main() == 0

    fake = fake_cli(monkeypatch, [answer("42")], ["--resume", "last", "what number?"])
    assert cli.main() == 0
    assert "remember 42" in str(fake.received[0])
    assert len(list(private_session_dir.glob("*.json"))) == 1  # same session, updated
