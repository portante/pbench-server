import pytest


def test_pbench_config():
    command = ["pbench-config"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1


def test_pbench_config_help():
    command = ["pbench-config", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert out.decode("UTF-8").startswith("Usage: pbench-config ")
    assert exitcode == 0


def test_pbench_agent_config(func_setup, monkeypatch):
    TMP = func_setup["tmp"]
    monkeypatch.setenv(
        "_PBENCH_AGENT_CONFIG", str(func_setup["cfg_dir"] / "pbench-agent.cfg")
    )
    command = ["pbench-config", "pbench_run", "pbench-agent"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert f"{TMP}/var/lib/pbench-agent".encode("UTF-8") in out
    assert (
        exitcode == 0
    ), f"command, '{command}', failed: {exitcode:d}; out={out!r}, err={err!r}"
