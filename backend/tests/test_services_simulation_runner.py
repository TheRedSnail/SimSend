"""SimulationRunner lifecycle tests: start failures, run ownership, terminal status."""

import json
import os
import subprocess

import pytest

from app.services.simulation_runner import RunnerStatus, SimulationRunner, SimulationRunState


class _FakeProcess:
    """Minimal Popen stand-in."""

    def __init__(self, pid=4242, returncode=None):
        self.pid = pid
        self.returncode = returncode

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode


@pytest.fixture
def runner(tmp_path, monkeypatch):
    sims = tmp_path / "simulations"
    sims.mkdir()
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(sims))
    for attr in ("_run_states", "_processes", "_action_queues", "_monitor_threads",
                 "_stdout_files", "_stderr_files", "_graph_memory_enabled"):
        monkeypatch.setattr(SimulationRunner, attr, {})
    monkeypatch.setattr(SimulationRunner, "_shutting_down", False)
    return SimulationRunner, sims


def _make_sim(sims, sim_id="sim_test", rounds_hours=1):
    sim_dir = sims / sim_id
    sim_dir.mkdir()
    (sim_dir / "simulation_config.json").write_text(json.dumps({
        "time_config": {"total_simulation_hours": rounds_hours, "minutes_per_round": 30}
    }), encoding="utf-8")
    return sim_id, sim_dir


def _read_state(sim_dir):
    return json.loads((sim_dir / "run_state.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------ start failures

def test_missing_config_fails_before_reserving(runner):
    cls, sims = runner
    (sims / "sim_noconf").mkdir()
    with pytest.raises(ValueError, match="config does not exist"):
        cls.start_simulation("sim_noconf")
    # Nothing was reserved, so the sim can't be stuck in STARTING
    assert not (sims / "sim_noconf" / "run_state.json").exists()


def test_graph_update_without_graph_id_fails_before_reserving(runner):
    cls, sims = runner
    sim_id, sim_dir = _make_sim(sims)
    with pytest.raises(ValueError, match="graph_id"):
        cls.start_simulation(sim_id, enable_graph_memory_update=True, graph_id=None)
    assert not (sim_dir / "run_state.json").exists()


def test_spawn_failure_marks_failed_and_allows_retry(runner, monkeypatch):
    cls, sims = runner
    sim_id, sim_dir = _make_sim(sims)

    def boom(*args, **kwargs):
        raise OSError("cannot spawn")

    monkeypatch.setattr(subprocess, "Popen", boom)

    with pytest.raises(OSError):
        cls.start_simulation(sim_id)
    state = _read_state(sim_dir)
    assert state["runner_status"] == "failed"
    assert "cannot spawn" in state["error"]

    # A second attempt is not rejected as "already running"
    with pytest.raises(OSError):
        cls.start_simulation(sim_id)


def test_start_uses_parallel_script_with_platform_flag(runner, monkeypatch):
    cls, sims = runner
    sim_id, sim_dir = _make_sim(sims)
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(cls, "_monitor_simulation", classmethod(lambda c, *a, **k: None))

    state = cls.start_simulation(sim_id, platform="reddit", max_rounds=3)
    assert os.path.basename(captured["cmd"][1]) == "run_parallel_simulation.py"
    assert "--reddit-only" in captured["cmd"]
    assert captured["cmd"][-2:] == ["--max-rounds", "3"]
    assert state.runner_status == RunnerStatus.RUNNING
    assert state.platform == "reddit"
    cls._stdout_files.pop(sim_id).close()


def test_concurrency_limit(runner, monkeypatch):
    cls, sims = runner
    sim_id, _ = _make_sim(sims)
    monkeypatch.setattr(cls, "_max_concurrent_simulations", classmethod(lambda c: 1))
    cls._processes["sim_other"] = _FakeProcess()
    with pytest.raises(ValueError, match="Too many simulations"):
        cls.start_simulation(sim_id)


def test_new_start_archives_previous_action_logs(runner):
    cls, sims = runner
    _, sim_dir = _make_sim(sims)
    (sim_dir / "twitter").mkdir()
    (sim_dir / "twitter" / "actions.jsonl").write_text('{"event_type": "simulation_end"}\n', encoding="utf-8")
    cls._archive_previous_run_logs(str(sim_dir))
    assert not (sim_dir / "twitter" / "actions.jsonl").exists()
    assert (sim_dir / "twitter" / "actions.prev.jsonl").exists()


# ---------------------------------------------------------- run ownership

def test_superseded_monitor_cannot_write_state(runner):
    cls, sims = runner
    sim_id, sim_dir = _make_sim(sims)
    old_proc, new_proc = _FakeProcess(pid=1), _FakeProcess(pid=2)

    new_state = SimulationRunState(simulation_id=sim_id, runner_status=RunnerStatus.RUNNING)
    cls._processes[sim_id] = new_proc
    assert cls._save_run_state(new_state, owner=new_proc) is True

    stale = SimulationRunState(simulation_id=sim_id, runner_status=RunnerStatus.COMPLETED)
    assert cls._save_run_state(stale, owner=old_proc) is False
    assert _read_state(sim_dir)["runner_status"] == "running"
    assert cls._run_states[sim_id] is new_state


def test_superseded_monitor_does_not_release_new_run(runner):
    cls, sims = runner
    sim_id, sim_dir = _make_sim(sims)
    old_proc, new_proc = _FakeProcess(pid=1, returncode=0), _FakeProcess(pid=2)
    cls._processes[sim_id] = new_proc

    cls._release_run(sim_id, old_proc, str(sim_dir))
    assert cls._processes[sim_id] is new_proc

    cls._release_run(sim_id, new_proc, str(sim_dir))
    assert sim_id not in cls._processes


# --------------------------------------------------------- terminal status

def _state(platform="parallel", **kw):
    return SimulationRunState(simulation_id="sim_test", platform=platform,
                              runner_status=RunnerStatus.RUNNING, **kw)


def test_finalize_requested_stop_is_stopped(runner, tmp_path):
    cls, _ = runner
    st = _state()
    st.runner_status = RunnerStatus.STOPPING
    cls._finalize_run_state(st, -15, str(tmp_path))
    assert st.runner_status == RunnerStatus.STOPPED


def test_finalize_all_platforms_done_is_completed_even_if_killed_later(runner, tmp_path):
    cls, _ = runner
    st = _state(twitter_completed=True, reddit_completed=True)
    cls._finalize_run_state(st, 143, str(tmp_path))
    assert st.runner_status == RunnerStatus.COMPLETED


def test_finalize_exit_zero_without_completion_is_failed(runner, tmp_path):
    cls, _ = runner
    st = _state(twitter_completed=True, reddit_completed=False)
    cls._finalize_run_state(st, 0, str(tmp_path))
    assert st.runner_status == RunnerStatus.FAILED
    assert "before all platforms finished" in st.error


def test_finalize_nonzero_exit_is_failed(runner, tmp_path):
    cls, _ = runner
    st = _state()
    cls._finalize_run_state(st, 1, str(tmp_path))
    assert st.runner_status == RunnerStatus.FAILED


def test_finalize_signal_exit_is_stopped(runner, tmp_path):
    cls, _ = runner
    st = _state()
    cls._finalize_run_state(st, 143, str(tmp_path))
    assert st.runner_status == RunnerStatus.STOPPED


def test_single_platform_completes_on_its_own_end_event(runner):
    cls, _ = runner
    st = _state(platform="twitter")
    cls._apply_event(st, "twitter", {"event_type": "simulation_end", "total_rounds": 2})
    assert st.runner_status == RunnerStatus.COMPLETED


def test_parallel_needs_both_platforms(runner):
    cls, _ = runner
    st = _state(platform="parallel")
    cls._apply_event(st, "twitter", {"event_type": "simulation_end"})
    assert st.runner_status == RunnerStatus.RUNNING
    cls._apply_event(st, "reddit", {"event_type": "simulation_end"})
    assert st.runner_status == RunnerStatus.COMPLETED


def test_failed_event_records_error_and_never_completes(runner):
    cls, _ = runner
    st = _state(platform="twitter")
    cls._apply_event(st, "twitter", {"event_type": "simulation_failed", "rounds_completed": 3,
                                     "total_rounds": 144, "error": "env.step failed"})
    assert st.runner_status == RunnerStatus.RUNNING
    assert "3/144" in st.error and "env.step failed" in st.error
    assert st.twitter_running is False


_CHILD = r'''
import json, os, sys
os.makedirs("twitter", exist_ok=True)
with open(os.path.join("twitter", "actions.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"round": 1, "agent_id": 1, "agent_name": "a", "action_type": "CREATE_POST"}) + "\n")
    f.write(json.dumps({"event_type": "round_end", "round": 1, "simulated_hours": 1}) + "\n")
    if sys.argv[1] == "ok":
        f.write(json.dumps({"event_type": "simulation_end", "total_rounds": 1}) + "\n")
    else:
        f.write(json.dumps({"event_type": "simulation_failed", "rounds_completed": 1,
                            "total_rounds": 4, "error": "boom"}) + "\n")
sys.exit(0 if sys.argv[1] == "ok" else 1)
'''


@pytest.mark.parametrize("mode, expected", [("ok", "completed"), ("fail", "failed")])
def test_monitor_end_to_end_with_real_child(runner, monkeypatch, mode, expected):
    import sys as _sys
    cls, sims = runner
    sim_id, sim_dir = _make_sim(sims)
    monkeypatch.setattr(cls, "MONITOR_INTERVAL", 0.05)
    state = SimulationRunState(simulation_id=sim_id, runner_status=RunnerStatus.RUNNING, platform="twitter")
    proc = subprocess.Popen([_sys.executable, "-c", _CHILD, mode], cwd=str(sim_dir))
    cls._processes[sim_id] = proc
    cls._save_run_state(state)

    cls._monitor_simulation(sim_id, proc, state)

    persisted = _read_state(sim_dir)
    assert persisted["runner_status"] == expected
    assert persisted["twitter_actions_count"] == 1
    if expected == "failed":
        assert "boom" in persisted["error"]
    assert sim_id not in cls._processes  # released


def test_read_action_log_applies_events(runner, tmp_path):
    cls, _ = runner
    log = tmp_path / "actions.jsonl"
    log.write_text(
        json.dumps({"round": 1, "event_type": "round_end", "simulated_hours": 1}) + "\n"
        + json.dumps({"round": 1, "agent_id": 3, "agent_name": "A", "action_type": "CREATE_POST"}) + "\n"
        + '{"partial": ',  # unflushed partial line must not be consumed
        encoding="utf-8",
    )
    st = _state(platform="twitter")
    pos = cls._read_action_log(str(log), 0, st, "twitter")
    assert st.twitter_current_round == 1
    assert st.twitter_actions_count == 1
    assert pos < log.stat().st_size
