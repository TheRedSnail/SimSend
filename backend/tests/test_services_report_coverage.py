"""The report agent is told how much of the campaign was actually simulated."""

import json
import sys
from pathlib import Path

import pytest

from app.config import Config
from app.services.report_agent import (
    CHAT_SYSTEM_PROMPT_TEMPLATE,
    EVIDENCE_RULES,
    PLAN_USER_PROMPT_TEMPLATE,
    SECTION_SYSTEM_PROMPT_TEMPLATE,
    ReportAgent,
    describe_simulation_coverage,
)
from app.services.simulation_runner import RunnerStatus, SimulationRunner, SimulationRunState

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from action_logger import PlatformActionLogger  # noqa: E402


@pytest.fixture
def sim(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(tmp_path))
    sim_dir = tmp_path / "sim_cov"
    sim_dir.mkdir()
    (sim_dir / "simulation_config.json").write_text(
        json.dumps({"time_config": {"minutes_per_round": 60, "total_simulation_hours": 168}})
    )
    state = SimulationRunState(
        simulation_id="sim_cov", runner_status=RunnerStatus.COMPLETED,
        current_round=12, total_rounds=12, total_simulation_hours=168,
        twitter_actions_count=29, reddit_actions_count=34,
    )
    monkeypatch.setattr(SimulationRunner, "get_run_state", classmethod(lambda cls, sid: state))
    logger = PlatformActionLogger("twitter", str(sim_dir))
    logger.log_action(0, 1, "Lisa de Vries", "CREATE_POST", {"content": "Trying GreenSip this week"})
    logger.log_action(3, 2, "Press", "LIKE_POST", {"post_content": "Trying GreenSip", "post_author_name": "Lisa de Vries"})
    logger.log_round_end(3, 1, simulated_hours=3)
    return state


def test_partial_run_is_described_as_partial(sim):
    text = describe_simulation_coverage("sim_cov")
    assert "12 hours of campaign time (12 rounds of 60 min)" in text
    assert "7 days (168 hours) campaign window" in text
    assert "29 on Twitter, 34 on Reddit" in text
    assert "Only the first 12 hours of the campaign were simulated" in text
    assert "  - Lisa de Vries — twitter: 1 posts" in text
    assert "  - Press — twitter: 1 post likes" in text


def test_full_run_has_no_projection_warning(sim):
    sim.current_round = 168
    text = describe_simulation_coverage("sim_cov")
    assert "7 days (168 hours) of campaign time" in text
    assert "Only the first" not in text


def test_missing_run_state_is_reported_as_unknown(monkeypatch):
    monkeypatch.setattr(SimulationRunner, "get_run_state", classmethod(lambda cls, sid: None))
    assert "Unknown" in describe_simulation_coverage("sim_missing")


def test_prompt_templates_include_coverage_and_rules():
    coverage = "[Simulation Coverage - what was actually simulated]\n- Simulated: 12 hours"
    plan = PLAN_USER_PROMPT_TEMPLATE.format(
        simulation_requirement="brief", simulation_coverage=coverage, evidence_rules=EVIDENCE_RULES,
        total_nodes=1, total_edges=1, entity_types=[], total_entities=1, related_facts_json="[]",
    )
    section = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
        report_title="t", report_summary="s", simulation_requirement="brief",
        simulation_coverage=coverage, evidence_rules=EVIDENCE_RULES,
        section_title="x", tools_description="tools",
    )
    chat = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
        simulation_requirement="brief", simulation_coverage=coverage,
        report_content="r", tools_description="tools",
    )
    for prompt in (plan, section, chat):
        assert coverage in prompt
    for prompt in (plan, section):
        assert "[Evidence Rules - Must Follow]" in prompt
    # Old format examples modelled an invented statistic and a quote that leaked into reports
    assert "68%" not in section
    assert "rigid and slow" not in section


def _agent():
    agent = ReportAgent.__new__(ReportAgent)
    agent.simulation_id = "sim_cov"
    return agent


def test_simulation_activity_tool_filters_the_action_log(sim):
    agent = _agent()
    posts = agent._simulation_activity({"agent_name": "lisa"})
    assert "1 matching actions" in posts
    assert 'Lisa de Vries CREATE_POST (posts): "Trying GreenSip this week"' in posts
    likes = agent._simulation_activity({"action_type": "like_post"})
    assert "Press LIKE_POST (post likes) (target: Lisa de Vries)" in likes
    assert "No matching actions" in agent._simulation_activity({"agent_name": "nobody"})


def test_trend_action_is_not_described_as_a_trending_post():
    from app.services.report_agent import format_action
    line = format_action({"platform": "reddit", "round": 12, "agent_name": "HEMA", "action_type": "TREND", "action_args": {}})
    assert "looked at what is trending; not evidence that their own post trended" in line
    assert "simulation_activity" in ReportAgent.VALID_TOOL_NAMES


def test_round_end_carries_elapsed_hours_into_run_state(tmp_path):
    PlatformActionLogger("twitter", str(tmp_path)).log_round_end(12, 3, simulated_hours=12.0)
    event = json.loads((tmp_path / "twitter" / "actions.jsonl").read_text().splitlines()[-1])
    assert event["simulated_hours"] == 12.0

    state = SimulationRunState(simulation_id="s", platform="parallel")
    SimulationRunner._apply_event(state, "twitter", event)
    assert state.twitter_simulated_hours == 12.0
    assert state.simulated_hours == 12.0
