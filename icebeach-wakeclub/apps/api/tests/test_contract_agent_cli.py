from __future__ import annotations

import io
import json
import shutil
import socket
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from apps.agents import api_client, cli, runners
from apps.agents.config import AgentsSettings
from apps.api.app.config import get_settings
from apps.api.app.dependencies import get_sheet_wrapper
from apps.api.app.main import app
from apps.api.app.routes import internal_agents
from conftest import MockSheetWrapper, make_test_settings


REPO_ROOT = Path(__file__).resolve().parents[4]
LEGACY_AGENTS = {
    "preflight_guard",
    "late_marker",
    "shift_snapshot",
    "ops_alert",
    "daily_brief",
    "intake_sync",
}


@pytest.fixture(autouse=True)
def offline_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError(
            "Agent CLI contracts must not use the network or send notifications"
        )

    original_connect = socket.socket.connect
    original_socketpair = socket.socketpair
    local = threading.local()

    def guarded_connect(sock, address):
        if getattr(local, "creating_socketpair", False):
            return original_connect(sock, address)
        return blocked(sock, address)

    def local_socketpair(*args, **kwargs):
        # Windows asyncio uses a loopback connection internally for socketpair.
        local.creating_socketpair = True
        try:
            return original_socketpair(*args, **kwargs)
        finally:
            local.creating_socketpair = False

    monkeypatch.setattr(socket, "socketpair", local_socketpair)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    monkeypatch.setattr(runners, "notify_all", blocked)
    monkeypatch.setattr(runners, "get_agents_settings", blocked)


@pytest.fixture
def agent_settings(tmp_path: Path) -> AgentsSettings:
    return AgentsSettings(
        api_base="http://testserver",
        secret="test-agents-secret",
        api_timeout_seconds=5,
        log_path=tmp_path / "agents.log",
        telegram_bot_token=None,
        telegram_owner_chat_id=None,
    )


def test_offline_guard_rejects_api_connections_and_external_transport() -> None:
    with socket.socket() as sock, pytest.raises(
        AssertionError, match="must not use the network"
    ):
        sock.connect(("127.0.0.1", 8000))
    with pytest.raises(AssertionError, match="must not use the network"):
        urllib.request.urlopen("http://testserver")


def test_list_includes_reminders_without_loading_settings_or_running_agents(
    capsys, monkeypatch
) -> None:
    for name in cli.AGENTS:
        monkeypatch.setattr(
            cli,
            f"run_{name}",
            Mock(side_effect=AssertionError("list must not run agents")),
        )

    assert cli.main(["list"]) == 0
    assert capsys.readouterr().out.splitlines() == sorted(
        LEGACY_AGENTS | {"shift_reminders"}
    )


@pytest.mark.parametrize("agent", sorted(LEGACY_AGENTS | {"shift_reminders"}))
def test_cli_dispatches_each_agent_once_and_prints_json(
    agent, monkeypatch, capsys
) -> None:
    payload = {"agent": agent, "admin_notices_sent": 0, "client_notices_sent": 0}
    runner = Mock(return_value=payload)
    monkeypatch.setattr(cli, f"run_{agent}", runner)

    assert cli.main(["run", "--agent", agent]) == 0
    assert json.loads(capsys.readouterr().out) == payload
    if agent == "daily_brief":
        runner.assert_called_once_with(mode="morning")
    else:
        runner.assert_called_once_with()


def test_daily_brief_evening_mode_is_preserved(monkeypatch, capsys) -> None:
    runner = Mock(return_value={"mode": "evening"})
    monkeypatch.setattr(cli, "run_daily_brief", runner)
    assert cli.main(["run", "--agent", "daily_brief", "--mode", "evening"]) == 0
    runner.assert_called_once_with(mode="evening")
    assert json.loads(capsys.readouterr().out) == {"mode": "evening"}


@pytest.mark.parametrize("argv", [["run"], ["run", "--agent", "unknown"], ["unknown"]])
def test_invalid_cli_arguments_fail_before_dispatch(argv, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(argv)
    assert exc.value.code == 2
    assert capsys.readouterr().out == ""


def test_reminders_runner_posts_to_existing_endpoint(
    agent_settings, monkeypatch
) -> None:
    payload = {"admin_notices_sent": 2, "client_notices_sent": 1}
    call = Mock(return_value=payload)
    monkeypatch.setattr(runners, "call_agents_api", call)
    assert runners.run_shift_reminders(agent_settings) == {
        "agent": "shift_reminders",
        **payload,
    }
    call.assert_called_once_with(
        agent_settings, "POST", "/internal/agents/shift-reminders"
    )


def test_missing_agent_secret_fails_without_request(
    agent_settings, monkeypatch, capsys
) -> None:
    from dataclasses import replace

    monkeypatch.setattr(
        runners, "get_agents_settings", lambda: replace(agent_settings, secret=None)
    )
    with pytest.raises(
        api_client.AgentsApiError, match="AGENTS_SECRET is not configured"
    ):
        cli.main(["run", "--agent", "shift_reminders"])
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("status", [401, 503])
def test_http_failure_is_not_reported_as_cli_success(
    status, agent_settings, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(runners, "get_agents_settings", lambda: agent_settings)

    def fail(request, *, timeout):
        raise urllib.error.HTTPError(
            request.full_url, status, "test failure", {}, io.BytesIO(b"test failure")
        )

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(api_client.AgentsApiError, match=f"HTTP {status}"):
        cli.main(["run", "--agent", "shift_reminders"])
    assert capsys.readouterr().out == ""


def test_unreachable_api_is_not_reported_as_cli_success(
    agent_settings, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(runners, "get_agents_settings", lambda: agent_settings)
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        Mock(side_effect=urllib.error.URLError("test timeout")),
    )
    with pytest.raises(api_client.AgentsApiError, match="test timeout"):
        cli.main(["run", "--agent", "shift_reminders"])
    assert capsys.readouterr().out == ""


def test_cli_to_authenticated_api_contract_in_memory(
    agent_settings, monkeypatch, capsys
) -> None:
    sheet = MockSheetWrapper()
    settings = make_test_settings()
    payload = {"admin_notices_sent": 0, "client_notices_sent": 0}
    process = Mock(return_value=payload)
    monkeypatch.setattr(internal_agents, "process_shift_reminders", process)
    monkeypatch.setattr(runners, "get_agents_settings", lambda: agent_settings)
    monkeypatch.setitem(app.dependency_overrides, get_sheet_wrapper, lambda: sheet)
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: settings)

    with TestClient(app) as client:

        def in_memory_request(request, *, timeout):
            assert (
                request.full_url == "http://testserver/internal/agents/shift-reminders"
            )
            assert request.get_method() == "POST"
            assert timeout == 5
            response = client.request(
                request.get_method(),
                "/internal/agents/shift-reminders",
                headers=dict(request.header_items()),
            )
            assert response.status_code == 200
            return io.BytesIO(response.content)

        monkeypatch.setattr(urllib.request, "urlopen", in_memory_request)
        assert cli.main(["run", "--agent", "shift_reminders"]) == 0

    process.assert_called_once_with(
        sheet,
        settings,
        club_id=settings.public_club_id,
        actor_staff_user_id=settings.agents_staff_user_id,
    )
    assert json.loads(capsys.readouterr().out) == {
        "agent": "shift_reminders",
        **payload,
    }


@pytest.mark.parametrize("header", [None, "invalid-test-secret"])
def test_reminder_api_rejects_unauthenticated_requests_in_memory(
    header, monkeypatch
) -> None:
    process = Mock(
        side_effect=AssertionError(
            "unauthenticated requests must not process reminders"
        )
    )
    monkeypatch.setattr(internal_agents, "process_shift_reminders", process)
    monkeypatch.setitem(app.dependency_overrides, get_sheet_wrapper, MockSheetWrapper)
    monkeypatch.setitem(app.dependency_overrides, get_settings, make_test_settings)
    with TestClient(app) as client:
        headers = {"X-Agents-Secret": header} if header else {}
        response = client.post("/internal/agents/shift-reminders", headers=headers)
    assert response.status_code == 401
    process.assert_not_called()


def _ps_path(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _powershell_results(source: str) -> list[object]:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if not executable:
        pytest.skip("PowerShell is needed for the mocked scheduler/wrapper contracts")
    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference = 'Stop'; " + source,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return [
        json.loads(line.removeprefix("__RESULT__"))
        for line in result.stdout.splitlines()
        if line.startswith("__RESULT__")
    ]


def test_powershell_schedule_registers_recurring_nonoverlapping_reminders() -> None:
    results = _powershell_results(
        """
        $script:Tasks = @()
        function New-ScheduledTaskAction {
            param($Execute, $Argument)
            [pscustomobject]@{Execute=$Execute; Argument=$Argument}
        }
        function New-ScheduledTaskTrigger {
            param([switch]$Daily, [switch]$Once, $At, [timespan]$RepetitionInterval, [timespan]$RepetitionDuration)
            [pscustomobject]@{
                Daily=[bool]$Daily; Once=[bool]$Once; At=[string]$At
                Repetition=[pscustomobject]@{Minutes=$RepetitionInterval.TotalMinutes; Days=$RepetitionDuration.TotalDays}
            }
        }
        function New-ScheduledTaskSettingsSet {
            param($MultipleInstances, [timespan]$ExecutionTimeLimit)
            [pscustomobject]@{MultipleInstances=$MultipleInstances; ExecutionMinutes=$ExecutionTimeLimit.TotalMinutes}
        }
        function Register-ScheduledTask {
            param($TaskName, $Action, $Trigger, $Settings, [switch]$Force)
            $script:Tasks += [pscustomobject]@{Name=$TaskName; Action=$Action; Trigger=$Trigger; Settings=$Settings; Force=[bool]$Force}
        }
        function Unregister-ScheduledTask { throw 'registration must not unregister tasks' }
    """
        + f"\n. {_ps_path(REPO_ROOT / 'scripts/schedule-agents.ps1')}\n"
        + """
        '__RESULT__' + (ConvertTo-Json -InputObject $script:Tasks -Depth 8 -Compress)
    """
    )
    tasks = {task["Name"]: task for task in results[0]}
    assert len(tasks) == 6
    reminders = tasks["IceBeach-Agent-ShiftReminders"]
    assert reminders["Trigger"] == {
        "Daily": True,
        "Once": False,
        "At": "00:00",
        "Repetition": {"Minutes": 1, "Days": 1},
    }
    assert reminders["Settings"] == {
        "MultipleInstances": "IgnoreNew",
        "ExecutionMinutes": 3,
    }
    assert reminders["Action"]["Execute"] == "powershell.exe"
    assert reminders["Action"]["Argument"].endswith('" -Agent shift_reminders')
    assert str(REPO_ROOT / "scripts/run-agent.ps1") in reminders["Action"]["Argument"]
    assert reminders["Force"] is True
    assert tasks["IceBeach-Agent-LateMarker"]["Trigger"]["Repetition"] == {
        "Minutes": 5,
        "Days": 14 / 24,
    }
    for name, time in {
        "IceBeach-Agent-Snapshot": "22:05",
        "IceBeach-Agent-BriefMorning": "07:00",
        "IceBeach-Agent-BriefEvening": "22:10",
        "IceBeach-Agent-OpsAlert": "06:55",
    }.items():
        assert tasks[name]["Trigger"]["Daily"] is True
        assert tasks[name]["Trigger"]["At"] == time
        assert tasks[name]["Settings"] is None


def test_powershell_unregister_includes_reminders_without_registering() -> None:
    results = _powershell_results(
        """
        function Register-ScheduledTask { throw 'unregister must not register tasks' }
        function Unregister-ScheduledTask {
            param($TaskName, [switch]$Confirm, $ErrorAction)
            '__RESULT__' + (ConvertTo-Json -InputObject $TaskName -Compress)
        }
    """
        + f"\n. {_ps_path(REPO_ROOT / 'scripts/schedule-agents.ps1')} -Unregister\n"
    )
    assert set(results) == {
        "IceBeach-Agent-LateMarker",
        "IceBeach-Agent-Snapshot",
        "IceBeach-Agent-BriefMorning",
        "IceBeach-Agent-BriefEvening",
        "IceBeach-Agent-OpsAlert",
        "IceBeach-Agent-ShiftReminders",
    }


@pytest.mark.parametrize(
    "agent,mode,exit_code",
    [
        ("shift_reminders", "morning", 0),
        ("shift_reminders", "morning", 9),
        ("daily_brief", "evening", 0),
    ],
)
def test_powershell_wrapper_dispatch_and_cleanup(agent, mode, exit_code) -> None:
    results = _powershell_results(
        """
        $env:PYTHONPATH = 'contract-original-pythonpath'
        $before = (Get-Location).Path
        $failure = $null
        function python {
            $script:PythonCall = [pscustomobject]@{Arguments=@($args); Directory=(Get-Location).Path; PythonPath=$env:PYTHONPATH}
    """
        + f"$global:LASTEXITCODE = {exit_code}\n}}\n"
        + f"""
        try {{ . {_ps_path(REPO_ROOT / 'scripts/run-agent.ps1')} -Agent {agent} -Mode {mode} }}
        catch {{ $failure = $_.Exception.Message }}
        '__RESULT__' + (ConvertTo-Json -Depth 6 -Compress -InputObject ([pscustomobject]@{{
            Call=$script:PythonCall; Failure=$failure; Before=$before; After=(Get-Location).Path; PythonPath=$env:PYTHONPATH
        }}))
    """
    )
    result = results[0]
    expected = ["-m", "apps.agents.cli", "run", "--agent", agent]
    if agent == "daily_brief":
        expected += ["--mode", mode]
    assert result["Call"]["Arguments"] == expected
    assert result["Call"]["Directory"] == str(REPO_ROOT / "icebeach-wakeclub")
    assert result["Call"]["PythonPath"] == "."
    assert result["Before"] == result["After"]
    assert result["PythonPath"] == "contract-original-pythonpath"
    if exit_code:
        assert result["Failure"] == f"Agent {agent} failed with exit code {exit_code}"
    else:
        assert result["Failure"] is None
