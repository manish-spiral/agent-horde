from horde import builtin_tools, cli
from horde.builtin_tools import load_memory, remember


def test_remember_appends_facts_and_needs_approval():
    assert remember.requires_approval({"fact": "x"})
    assert load_memory() is None
    remember.function("User prefers   tabs\n over spaces")
    remember.function("Project uses uv")
    assert load_memory() == "- User prefers tabs over spaces\n- Project uses uv"


def test_memory_is_loaded_into_new_conversations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    remember.function("User's name is Manish")
    instructions = cli.project_instructions()
    assert "Things you remembered" in instructions and "User's name is Manish" in instructions
