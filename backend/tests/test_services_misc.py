"""SimulationManager persistence, report-agent tool-call parsing, Zep updater backpressure and digests."""

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
    u = ZepGraphMemoryUpdater("graph_x", api_key="test", mode="full")
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


class _FakeLLM:
    def __init__(self, reply="summary", fail=False):
        self.reply, self.fail, self.calls = reply, fail, []

    def chat(self, messages, **kwargs):
        if self.fail:
            raise ConnectionError("llm down")
        self.calls.append((messages[-1]["content"], kwargs))
        return self.reply


def _act(round_num, action_type="CREATE_POST", platform="twitter", **args):
    return AgentActivity(platform=platform, agent_id=1, agent_name="Ann", action_type=action_type,
                         action_args=args or {"content": f"post in round {round_num}"},
                         round_num=round_num, timestamp="t")


@pytest.fixture
def digester(monkeypatch):
    monkeypatch.setattr(ZepGraphMemoryUpdater, "RETRY_DELAY", 0)
    u = ZepGraphMemoryUpdater("graph_x", api_key="test", mode="digest", minutes_per_round=60)
    u.client = _FakeZep()
    u._llm = _FakeLLM()
    return u


def test_mode_defaults_to_digest_and_reads_env(monkeypatch):
    monkeypatch.delenv("ZEP_ACTIVITY_MODE", raising=False)
    assert ZepGraphMemoryUpdater("g", api_key="test").mode == "digest"
    monkeypatch.setenv("ZEP_ACTIVITY_MODE", "full")
    assert ZepGraphMemoryUpdater("g", api_key="test").mode == "full"
    monkeypatch.setenv("ZEP_ACTIVITY_MODE", "bogus")
    assert ZepGraphMemoryUpdater("g", api_key="test").mode == "digest"


def test_digest_sends_one_summary_when_the_next_window_starts(digester):
    for r in (0, 2, 6):  # opening posts, then rounds covering hours 1-2 and 5-6
        digester._buffer_for_digest(_act(r), "twitter")
    assert digester.client.graph.calls == []  # window 0-6h still open
    digester._buffer_for_digest(_act(7), "twitter")
    assert digester.client.graph.calls == ["Day 1, hours 0-6 of the campaign, on Twitter: summary"]
    prompt, kwargs = digester._llm.calls[0]
    assert prompt.count("Ann posted:") == 3
    assert kwargs["reasoning"] is False
    assert digester.get_stats()["items_sent"] == 3


def test_digest_windows_follow_simulated_time(digester):
    digester.minutes_per_round = 30  # 12 rounds per 6-hour window
    assert digester._window_of(_act(12)) == 0
    assert digester._window_of(_act(13)) == 1
    digester.minutes_per_round = 60
    assert digester._window_of(_act(0)) == 0  # opening posts
    assert digester._window_of(_act(48)) == 7  # day 2, hours 42-48
    assert digester._window_of(_act(168)) == 27  # last round of a week, not a day 8 window


def test_digest_lines_drop_parent_text_and_searches():
    like = _act(1, "LIKE_POST", post_author_name="Bob", post_content="x" * 900)
    assert like.to_digest_line() == "Ann liked a post by Bob"
    reply = _act(1, "CREATE_COMMENT", content="y " * 400, post_author_name="Bob", post_content="z" * 900)
    line = reply.to_digest_line()
    assert line.startswith('Ann replied to Bob: "y y') and "z" not in line
    assert len(line) < AgentActivity.DIGEST_OWN_TEXT_CHARS + 40
    quote = _act(1, "QUOTE_POST", quote_content="mine", original_author_name="Bob", original_content="theirs")
    assert quote.to_digest_line() == 'Ann quoted Bob: "mine"'
    assert _act(1, "SEARCH_POSTS", query="velora").to_digest_line() is None


def test_digest_falls_back_to_activity_lines_when_llm_fails(digester):
    digester._llm = _FakeLLM(fail=True)
    digester._send_digest([_act(0), _act(1)], "reddit")
    (sent,) = digester.client.graph.calls
    assert sent.startswith("Day 1, hours 0-6 of the campaign, on Reddit:\n")
    assert sent.count("Ann posted:") == 2


def test_digest_flush_summarises_each_open_window(digester):
    for r in (0, 7):
        digester.add_activity(_act(r))
    digester.add_activity(_act(0, platform="reddit"))
    digester._flush_remaining(time.monotonic() + 5)
    assert sorted(c.split(":")[0] for c in digester.client.graph.calls) == [
        "Day 1, hours 0-6 of the campaign, on Reddit",
        "Day 1, hours 0-6 of the campaign, on Twitter",
        "Day 1, hours 6-12 of the campaign, on Twitter",
    ]
    assert len(digester._llm.calls) == 3



def test_zep_search_query_is_cut_to_zeps_limit():
    from types import SimpleNamespace
    from app.services.zep_tools import ZepToolsService
    seen = {}

    def search(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(edges=[], nodes=[])

    tools = ZepToolsService.__new__(ZepToolsService)
    tools.client = SimpleNamespace(graph=SimpleNamespace(search=search))
    result = tools.search_graph("g", "q" * 900)
    assert len(seen["query"]) == ZepToolsService.ZEP_MAX_QUERY_CHARS
    assert result.query == "q" * 900



def _wait_for(cond, timeout=5):
    deadline = time.monotonic() + timeout
    while not cond() and time.monotonic() < deadline:
        time.sleep(0.02)
    return cond()


def test_platform_end_sends_the_open_window_without_stopping(digester):
    digester.start()
    try:
        digester.add_activity(_act(165))
        digester.add_activity(_act(166, platform="reddit"))
        digester.end_platform("twitter")
        assert _wait_for(lambda: digester.client.graph.calls)
        assert digester.client.graph.calls == ["Day 7, hours 162-168 of the campaign, on Twitter: summary"]
        assert digester.get_stats()["buffer_sizes"]["reddit"] == 1  # reddit is still running
    finally:
        digester.stop(flush_timeout=2)


def test_platform_end_sends_a_partial_batch_in_full_mode(updater):
    updater.start()
    try:
        for i in range(3):
            updater.add_activity(_activity(i))
        updater.end_platform("twitter")
        assert _wait_for(lambda: updater.client.graph.calls)
        assert len(updater.client.graph.calls[0].splitlines()) == 3
    finally:
        updater.stop(flush_timeout=2)
