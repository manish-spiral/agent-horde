from horde.loop import CLEARED, clear_old_tool_results


def conversation(results):
    return [{"role": "user", "content": "go"}] + [
        {"role": "tool", "tool_call_id": str(i), "content": "x" * 100} for i in range(results)]


def test_small_conversations_are_untouched():
    messages = conversation(10)
    assert clear_old_tool_results(messages, max_chars=10_000, keep=2) == 0
    assert all(m["content"] != CLEARED for m in messages)


def test_old_tool_results_are_cleared_newest_kept():
    messages = conversation(10)
    assert clear_old_tool_results(messages, max_chars=500, keep=2) == 8
    assert [m["content"] == CLEARED for m in messages[1:]] == [True] * 8 + [False] * 2
    assert messages[0]["content"] == "go"
    assert clear_old_tool_results(messages, max_chars=500, keep=2) == 0  # nothing left to clear
