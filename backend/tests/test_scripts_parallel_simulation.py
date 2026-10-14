"""Tests for the simulation subprocess script (OASIS is stubbed; no LLM/network)."""

import asyncio
import json
import os
import sqlite3
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

sim = pytest.importorskip("run_parallel_simulation")
from action_logger import PlatformActionLogger  # noqa: E402


def _events(sim_dir, platform):
    path = os.path.join(sim_dir, platform, "actions.jsonl")
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ------------------------------------------------------------- exit codes

def _result(outcome):
    r = sim.PlatformSimulation("twitter")
    r.outcome = outcome
    return r


def test_exit_codes():
    assert sim.summarize_exit_code([_result("completed")], False) == sim.EXIT_OK
    assert sim.summarize_exit_code([_result("completed"), _result("failed")], False) == sim.EXIT_FAILED
    assert sim.summarize_exit_code([_result("stopped")], False) == sim.EXIT_STOPPED
    assert sim.summarize_exit_code([_result("completed")], True) == sim.EXIT_STOPPED


def test_platform_flags_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        sim.parse_args(["--config", "c.json", "--twitter-only", "--reddit-only"])


def test_missing_config_returns_nonzero():
    assert asyncio.run(sim.main(["--config", "definitely_missing.json"])) == sim.EXIT_BAD_ARGS


# ------------------------------------------------- platform loop outcomes

class _FakeEnv:
    def __init__(self, fail_steps):
        self.fail_steps = fail_steps
        self.steps = 0
        self.agent_graph = self

    async def reset(self):
        pass

    async def step(self, actions):
        self.steps += 1
        if self.steps > self.fail_steps[0] and self.steps <= self.fail_steps[1]:
            raise RuntimeError("LLM provider exploded")

    def get_agent(self, agent_id):
        return f"agent{agent_id}"

    def get_agents(self):
        return []


@pytest.fixture
def stub_oasis(tmp_path, monkeypatch):
    (tmp_path / "twitter_profiles.csv").write_text("id\n", encoding="utf-8")
    monkeypatch.setattr(sim, "create_model", lambda config, use_boost=False: None)

    async def fake_graph(**kwargs):
        return _FakeEnv((10**9, 10**9))

    monkeypatch.setattr(sim, "generate_twitter_agent_graph", fake_graph)
    monkeypatch.setattr(sim, "get_active_agents_for_round", lambda env, config, hour, rnd: [(0, "a0")])
    monkeypatch.setattr(sim, "STEP_RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(sim, "_shutdown_event", None)

    def install_env(env):
        monkeypatch.setattr(sim.oasis, "make", lambda **kwargs: env)

    return tmp_path, install_env


CONFIG = {"time_config": {"total_simulation_hours": 2, "minutes_per_round": 30}}  # 4 rounds


def _run(sim_dir, max_rounds=None):
    logger = PlatformActionLogger("twitter", str(sim_dir))
    return asyncio.run(sim.run_platform_simulation("twitter", CONFIG, str(sim_dir), logger, None, max_rounds))


def test_completed_run_logs_simulation_end(stub_oasis):
    sim_dir, install_env = stub_oasis
    install_env(_FakeEnv((10**9, 10**9)))
    result = _run(sim_dir)
    assert result.outcome == "completed"
    assert result.rounds_completed == 4
    assert _events(sim_dir, "twitter")[-1]["event_type"] == "simulation_end"


def test_transient_step_error_is_retried(stub_oasis):
    sim_dir, install_env = stub_oasis
    install_env(_FakeEnv((1, 2)))  # 2nd call fails once, retry succeeds
    result = _run(sim_dir)
    assert result.outcome == "completed"


def test_persistent_step_error_fails_instead_of_completing(stub_oasis):
    sim_dir, install_env = stub_oasis
    install_env(_FakeEnv((2, 10**9)))  # round 3 onwards always fails
    result = _run(sim_dir)
    assert result.outcome == "failed"
    assert result.rounds_completed == 2
    last = _events(sim_dir, "twitter")[-1]
    assert last["event_type"] == "simulation_failed"
    assert last["rounds_completed"] == 2
    assert not any(e.get("event_type") == "simulation_end" for e in _events(sim_dir, "twitter"))


def test_shutdown_logs_stopped_not_end(stub_oasis, monkeypatch):
    sim_dir, install_env = stub_oasis
    install_env(_FakeEnv((10**9, 10**9)))

    class _SetEvent:
        def is_set(self):
            return True

    monkeypatch.setattr(sim, "_shutdown_event", _SetEvent())
    result = _run(sim_dir)
    assert result.outcome == "stopped"
    assert _events(sim_dir, "twitter")[-1]["event_type"] == "simulation_stopped"


def test_missing_profiles_fail_explicitly(tmp_path, monkeypatch):
    monkeypatch.setattr(sim, "create_model", lambda config, use_boost=False: None)
    result = _run(tmp_path)
    assert result.outcome == "failed"
    assert _events(tmp_path, "twitter")[-1]["event_type"] == "simulation_failed"


# --------------------------------------------------------- IPC / interviews

def _make_trace_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE trace (user_id INTEGER, action TEXT, info TEXT, created_at TEXT)")
    conn.executemany("INSERT INTO trace VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()


class _InterviewEnv:
    """env.step that records an interview answer only for agents in `answers`."""

    def __init__(self, db_path, answers):
        self.db_path = db_path
        self.answers = answers

    async def step(self, actions):
        conn = sqlite3.connect(self.db_path)
        for agent_id in self.answers:
            conn.execute("INSERT INTO trace VALUES (?, ?, ?, ?)",
                         (agent_id, sim.ActionType.INTERVIEW.value,
                          json.dumps({"response": f"fresh {agent_id}"}), "2"))
        conn.commit()
        conn.close()


class _Graph:
    def get_agent(self, agent_id):
        return f"agent{agent_id}"


def test_batch_interview_never_returns_stale_answers(tmp_path):
    db = str(tmp_path / "twitter_simulation.db")
    interview = sim.ActionType.INTERVIEW.value
    _make_trace_db(db, [(1, interview, json.dumps({"response": "OLD 1"}), "1"),
                        (2, interview, json.dumps({"response": "OLD 2"}), "1")])
    handler = sim.ParallelIPCHandler(str(tmp_path), twitter_env=_InterviewEnv(db, answers=[1]),
                                     twitter_agent_graph=_Graph())

    ok = asyncio.run(handler.handle_batch_interview(
        "cmd1", [{"agent_id": 1, "prompt": "q"}, {"agent_id": 2, "prompt": "q"}], platform="twitter"))
    assert ok
    with open(tmp_path / "ipc_responses" / "cmd1.json", encoding="utf-8") as f:
        response = json.load(f)
    results = response["result"]["results"]
    assert results["twitter_1"]["response"] == "fresh 1"
    assert results["twitter_2"]["response"] is None
    assert "error" in results["twitter_2"]


def test_process_commands_reports_idle_and_close(tmp_path):
    handler = sim.ParallelIPCHandler(str(tmp_path))
    assert asyncio.run(handler.process_commands()) == (False, True)
    sim.write_json_atomic(os.path.join(handler.commands_dir, "c1.json"),
                          {"command_id": "c1", "command_type": "close_env", "args": {}})
    assert asyncio.run(handler.process_commands()) == (True, False)


def test_status_file_written_atomically(tmp_path):
    handler = sim.ParallelIPCHandler(str(tmp_path))
    handler.update_status("alive")
    with open(handler.status_file, encoding="utf-8") as f:
        assert json.load(f)["status"] == "alive"
    assert not [n for n in os.listdir(tmp_path) if n.endswith(".tmp")]


# ------------------------------------------------------------- agent context cap

class _FakeCreator:
    def __init__(self):
        self._token_limit = 1_000_000


class _FakeMemory:
    def __init__(self):
        self.creator = _FakeCreator()

    def get_context_creator(self):
        return self.creator


class _FakeAgent:
    def __init__(self):
        self.memory = _FakeMemory()


class _FakeGraph:
    def __init__(self, agents):
        self._agents = agents

    def get_agents(self):
        return list(enumerate(self._agents))


def test_cap_agent_context_sets_every_agents_limit():
    agents = [_FakeAgent(), _FakeAgent(), object()]  # the last has no memory
    assert sim.cap_agent_context(_FakeGraph(agents), 12000) == 2
    assert all(a.memory.creator._token_limit == 12000 for a in agents[:2])


def test_cap_agent_context_disabled():
    agent = _FakeAgent()
    assert sim.cap_agent_context(_FakeGraph([agent]), None) == 0
    assert agent.memory.creator._token_limit == 1_000_000


@pytest.mark.parametrize("raw, expected", [
    (None, sim.DEFAULT_SWARM_CONTEXT_TOKENS),
    ("", sim.DEFAULT_SWARM_CONTEXT_TOKENS),
    ("8000", 8000),
    ("0", None),
    ("lots", sim.DEFAULT_SWARM_CONTEXT_TOKENS),
])
def test_swarm_context_token_limit_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("SWARM_CONTEXT_TOKEN_LIMIT", raising=False)
    else:
        monkeypatch.setenv("SWARM_CONTEXT_TOKEN_LIMIT", raw)
    assert sim.swarm_context_token_limit() == expected


def test_capped_camel_context_drops_oldest_turns_and_keeps_system_prompt():
    """Guards the private attribute against camel changes: the real context
    creator must truncate against the value cap_agent_context sets."""
    camel_memories = pytest.importorskip("camel.memories")
    from camel.messages import BaseMessage
    from camel.types import OpenAIBackendRole
    from camel.utils import BaseTokenCounter

    class WordCounter(BaseTokenCounter):
        def count_tokens_from_messages(self, messages):
            return sum(len(str(m.get("content", "")).split()) for m in messages)

        def encode(self, text):
            return text.split()

        def decode(self, token_ids):
            return " ".join(token_ids)

    creator = camel_memories.ScoreBasedContextCreator(WordCounter(), 1_000_000)
    memory = camel_memories.ChatHistoryMemory(creator)
    memory.write_records([camel_memories.MemoryRecord(
        message=BaseMessage.make_assistant_message("system", "persona profile"),
        role_at_backend=OpenAIBackendRole.SYSTEM)])
    for i in range(20):
        memory.write_records([camel_memories.MemoryRecord(
            message=BaseMessage.make_user_message("User", f"round {i} " + "feed " * 50),
            role_at_backend=OpenAIBackendRole.USER)])

    uncapped, uncapped_tokens = memory.get_context()

    agent = _FakeAgent()
    agent.memory = memory
    sim.cap_agent_context(_FakeGraph([agent]), 300)
    capped, capped_tokens = memory.get_context()

    assert len(capped) < len(uncapped)
    assert capped_tokens <= 300 < uncapped_tokens
    assert capped[0]["content"] == "persona profile"
    # The newest turns survive. (Their order here is arbitrary: the records
    # were written in the same instant, so their timestamps tie.)
    kept = {int(m["content"].split()[1]) for m in capped[1:]}
    assert kept == set(range(20 - len(kept), 20))
