import pytest

from horde.builtin_tools import DEFAULT_TOOLS, update_plan


def test_update_plan_reports_progress():
    result = update_plan.function("[x] read the file\n\n  [~] count features\n[ ] multiply")
    assert result == ("Plan updated (1/3 done):\n"
                      "[x] read the file\n[~] count features\n[ ] multiply")


@pytest.mark.parametrize("plan", ["", "read the file", "[x] ok\n- not marked"])
def test_update_plan_rejects_unmarked_items(plan):
    with pytest.raises(ValueError, match=r"must start with"):
        update_plan.function(plan)


def test_update_plan_is_available_and_needs_no_approval():
    assert update_plan in DEFAULT_TOOLS
    assert not update_plan.requires_approval({"plan": "[ ] x"})
