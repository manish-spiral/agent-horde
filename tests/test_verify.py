from horde import cli
from test_loop import FakeModel, answer


def run(monkeypatch, replies, *argv):
    fake = FakeModel(replies)
    monkeypatch.setattr(cli, "create_model", lambda *args: fake)
    monkeypatch.setattr("sys.argv", ["horde", *argv, "task"])
    return cli.main(), fake


def test_failed_check_goes_back_to_the_agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # The check passes only once a file named "fixed" exists; the fake "fixes" it on try 2.
    check = "test -f fixed || (echo 'not fixed yet'; exit 1)"

    class FixOnSecondCall(FakeModel):
        def complete(self, messages, tools):
            if len(self.received) == 1:
                (tmp_path / "fixed").touch()
            return super().complete(messages, tools)

    fake = FixOnSecondCall([answer("first try"), answer("fixed it")])
    monkeypatch.setattr(cli, "create_model", lambda *args: fake)
    monkeypatch.setattr("sys.argv", ["horde", "--verify", check, "task"])

    assert cli.main() == 0
    assert len(fake.received) == 2
    feedback = fake.received[1][-1]["content"]
    assert "failed after your last answer" in feedback and "not fixed yet" in feedback


def test_passing_check_needs_no_retry(monkeypatch):
    code, fake = run(monkeypatch, [answer("done")], "--verify", "true")
    assert code == 0 and len(fake.received) == 1


def test_gives_up_after_retries(monkeypatch):
    code, fake = run(monkeypatch, [answer("nope")] * 4, "--verify", "false")
    assert code == 1 and len(fake.received) == 1 + cli.VERIFY_RETRIES
