"""SimulationManager persistence, report-agent tool-call parsing, Zep updater backpressure."""

import json
import os
import time

import pytest

from app.services.report_agent import ReportAgent
from app.services.simulation_manager import SimulationManager, SimulationStatus
from app.services.zep_graph_memory_updater import AgentActivity, ZepGraphMemoryUpdater
from app.services.zep_tools import NodeInfo, PanoramaResult


# -------------------------------------------------------- SimulationManager

@pytest.fixture
def manager(tmp_path, monkeypatch):
    sims = tmp_path / "simulations"
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(sims))
    monkeypatch.setattr(SimulationManager, "_cache", {})
    return SimulationManager(), sims


def test_reading_unknown_simulation_creates_nothing(manager):
    mgr, sims = manager
    assert mgr.get_simulation("sim_doesnotexist") is None
    assert mgr.get_simulation_config("sim_doesnotexist") is None
    assert not (sims / "sim_doesnotexist").exists()


def test_state_roundtrip_and_cache_shared_across_instances(manager):
    mgr, _ = manager
    state = mgr.create_simulation(project_id="p1", graph_id="g1")
    other = SimulationManager()
    loaded = other.get_simulation(state.simulation_id)
    assert loaded is state  # served from the process-wide cache
    assert loaded.project_id == "p1"


def test_cache_invalidated_by_external_write(manager):
    mgr, sims = manager
    state = mgr.create_simulation(project_id="p1", graph_id="g1")
    state_file = sims / state.simulation_id / "state.json"
    data = json.loads(state_file.read_text(encoding="utf-8"))
    data["status"] = "stopped"
    time.sleep(0.01)
    state_file.write_text(json.dumps(data), encoding="utf-8")
    os.utime(state_file, ns=(time.time_ns(), time.time_ns() + 10_000_000))
    assert SimulationManager().get_simulation(state.simulation_id).status == SimulationStatus.STOPPED


def test_list_skips_corrupt_state(manager):
    mgr, sims = manager
    good = mgr.create_simulation(project_id="p1", graph_id="g1")
    bad_dir = sims / "sim_corrupt"
    bad_dir.mkdir()
    (bad_dir / "state.json").write_text('{"truncated": ', encoding="utf-8")
    ids = [s.simulation_id for s in mgr.list_simulations()]
    assert ids == [good.simulation_id]


# ----------------------------------------------------- report agent parsing

@pytest.fixture
def agent():
    # Parsing helpers only need class-level attributes; skip the heavy __init__.
    return ReportAgent.__new__(ReportAgent)


@pytest.mark.parametrize("payload, expected", [
    ('<tool_call>{"name": "quick_search", "parameters": {"query": "q"}}</tool_call>',
     {"name": "quick_search", "parameters": {"query": "q"}}),
    ('<tool_call>{"tool": "panorama_search", "params": {"query": "q"}}</tool_call>',
     {"name": "panorama_search", "parameters": {"query": "q"}}),
    ('<tool_call>{"tool_name": "insight_forge", "arguments": "{\\"query\\": \\"q\\"}"}</tool_call>',
     {"name": "insight_forge", "parameters": {"query": "q"}}),
    ('<tool_call>{"function": {"name": "quick_search", "arguments": {"query": "q"}}}</tool_call>',
     {"name": "quick_search", "parameters": {"query": "q"}}),
    ('Thinking...\n{"name": "quick_search", "args": {"query": "q"}}',
     {"name": "quick_search", "parameters": {"query": "q"}}),
])
def test_tool_call_variants_are_normalized(agent, payload, expected):
    assert agent._parse_tool_calls(payload) == [expected]


def test_unknown_or_malformed_tool_calls_are_ignored(agent):
    assert agent._parse_tool_calls('<tool_call>{"tool": "rm_rf", "args": {}}</tool_call>') == []
    assert agent._parse_tool_calls('<tool_call>{"parameters": {}}</tool_call>') == []
    assert agent._parse_tool_calls('<tool_call>not json</tool_call>') == []


def test_tool_result_truncation(agent):
    assert agent._truncate_tool_result("short", 100) == "short"
    out = agent._truncate_tool_result("x" * 500, 100)
    assert out.startswith("x" * 100) and "400 more characters omitted" in out
    assert agent._truncate_tool_result(None) == ""


def test_panorama_text_is_capped():
    nodes = [NodeInfo(uuid=str(i), name=f"n{i}", labels=["Entity", "Brand"], summary="", attributes={})
             for i in range(1000)]
    result = PanoramaResult(query="q", all_nodes=nodes, active_facts=[f"fact {i}" for i in range(1000)])
    text = result.to_text()
    assert "n999" not in text
    assert "more entities (omitted)" in text
    assert "more (omitted)" in text


# ------------------------------------------------------ Zep memory updater

class _FakeGraph:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def add(self, graph_id, type, data):
        if self.fail:
            raise ConnectionError("down")
        self.calls.append(data)


class _FakeZep:
    def __init__(self, fail=False):
        self.graph = _FakeGraph(fail)


def _activity(i, platform="twitter"):
    return AgentActivity(platform=platform, agent_id=i, agent_name=f"a{i}", action_type="CREATE_POST",
                         action_args={"content": f"post {i}"}, round_num=1, timestamp="t")


@pytest.fixture
def updater(monkeypatch):
    monkeypatch.setattr(ZepGraphMemoryUpdater, "MAX_QUEUE_SIZE", 10)
    monkeypatch.setattr(ZepGraphMemoryUpdater, "RETRY_DELAY", 0)
    u = ZepGraphMemoryUpdater("graph_x", api_key="test")
    u.client = _FakeZep()
    return u


def test_queue_is_bounded_and_drops_oldest(updater):
    for i in range(25):
        updater.add_activity(_activity(i))
    stats = updater.get_stats()
    assert stats["queue_size"] == 10
    assert stats["dropped_count"] == 15
    assert updater._activity_queue.get_nowait().agent_id == 15


def test_flush_sends_backlog_in_chunks(updater):
    for i in range(10):
        updater.add_activity(_activity(i))
    updater.FLUSH_CHUNK_SIZE = 4
    updater._flush_remaining(time.monotonic() + 5)
    sizes = [len(c.splitlines()) for c in updater.client.graph.calls]
    assert sizes == [4, 4, 2]
    assert updater.get_stats()["items_sent"] == 10


def test_flush_respects_deadline(updater):
    for i in range(5):
        updater.add_activity(_activity(i))
    updater._flush_remaining(time.monotonic() - 1)  # already past the deadline
    assert updater.client.graph.calls == []
    assert updater.get_stats()["dropped_count"] == 5


def test_stop_is_bounded_when_zep_is_down(updater, monkeypatch):
    monkeypatch.setattr("app.utils.retry.time.sleep", lambda s: None)
    updater.client = _FakeZep(fail=True)
    updater.start()
    for i in range(10):
        updater.add_activity(_activity(i))
    started = time.monotonic()
    updater.stop(flush_timeout=2)
    assert time.monotonic() - started < 6
    assert updater.get_stats()["items_sent"] == 0
