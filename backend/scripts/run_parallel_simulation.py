"""
OASIS Dual-Platform Parallel Simulation Script
Runs Twitter and Reddit simulations simultaneously, reading the same config file

Features:
- Dual-platform (Twitter + Reddit) parallel simulation
- Does not close environment immediately after simulation; enters command-waiting mode
- Supports receiving Interview commands via IPC
- Supports single Agent interviews and batch interviews
- Supports remote close environment command

Usage:
    python run_parallel_simulation.py --config simulation_config.json
    python run_parallel_simulation.py --config simulation_config.json --no-wait  # Close immediately after completion
    python run_parallel_simulation.py --config simulation_config.json --twitter-only
    python run_parallel_simulation.py --config simulation_config.json --reddit-only

Log structure:
    sim_xxx/
    ├── twitter/
    │   └── actions.jsonl    # Twitter platform action log
    ├── reddit/
    │   └── actions.jsonl    # Reddit platform action log
    ├── simulation.log       # Main simulation process log
    └── run_state.json       # Run state (for API queries)
"""

# ============================================================
# Fix Windows encoding issues: set UTF-8 encoding before all imports
# This fixes OASIS third-party libraries reading files without specifying encoding
# ============================================================
import sys
import os

if sys.platform == 'win32':
    # Set Python default I/O encoding to UTF-8
    # This affects all open() calls that don't specify encoding
    os.environ.setdefault('PYTHONUTF8', '1')
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    
    # Reconfigure standard output streams to UTF-8 (fix console encoding issues)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    
    # Force set default encoding (affects open() function's default encoding)
    # Note: This needs to be set at Python startup; runtime setting may not take effect
    # Therefore we also need to monkey-patch the built-in open function
    import builtins
    _original_open = builtins.open
    
    def _utf8_open(file, mode='r', buffering=-1, encoding=None, errors=None, 
                   newline=None, closefd=True, opener=None):
        """
        Wrap open() function to default to UTF-8 encoding for text mode.
        This fixes third-party libraries (like OASIS) reading files without specifying encoding.
        """
        # Only set default encoding for text mode (non-binary) when encoding is not specified
        if encoding is None and 'b' not in mode:
            encoding = 'utf-8'
        return _original_open(file, mode, buffering, encoding, errors, 
                              newline, closefd, opener)
    
    builtins.open = _utf8_open

import argparse
import asyncio
import dataclasses
import json
import logging
import random
import signal
import sqlite3
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple


# Global variables: for signal handling
_shutdown_event = None
_cleanup_done = False

# Add backend directory to path
# Script is fixed in backend/scripts/ directory
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
_project_root = os.path.abspath(os.path.join(_backend_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

# Load .env file from project root directory (contains LLM_API_KEY and other configs)
from dotenv import load_dotenv
_env_file = os.path.join(_project_root, '.env')
if os.path.exists(_env_file):
    load_dotenv(_env_file)
    print(f"Loaded environment config: {_env_file}")
else:
    # Try loading backend/.env
    _backend_env = os.path.join(_backend_dir, '.env')
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)
        print(f"Loaded environment config: {_backend_env}")


class MaxTokensWarningFilter(logging.Filter):
    """Filter out camel-ai max_tokens warnings (we intentionally don't set max_tokens, letting the model decide)"""
    
    def filter(self, record):
        message = record.getMessage()
        # Filter out log entries containing max_tokens warnings
        if "max_tokens" in message and "Invalid or missing" in message:
            return False
        # Expected on every call once an agent's history exceeds the context
        # cap (see cap_agent_context); not worth a line per call.
        if message.startswith("Context truncation performed"):
            return False
        return True


# Install the filter. A filter on the root *logger* only screens records logged
# directly to root — NOT records propagated up from a child logger (those are
# handled by root's handlers, which apply their own filters). camel emits the
# max_tokens warning through its own logger, so attach the filter to the camel
# logger tree and to the root logger's handlers as well.
_max_tokens_filter = MaxTokensWarningFilter()


def _install_max_tokens_filter():
    root = logging.getLogger()
    if _max_tokens_filter not in root.filters:
        root.addFilter(_max_tokens_filter)
    for _h in root.handlers:
        if _max_tokens_filter not in _h.filters:
            _h.addFilter(_max_tokens_filter)
    camel_logger = logging.getLogger("camel")
    if _max_tokens_filter not in camel_logger.filters:
        camel_logger.addFilter(_max_tokens_filter)


_install_max_tokens_filter()


def disable_oasis_logging():
    """
    Disable verbose OASIS library log output.
    OASIS logs are too verbose (recording every agent's observations and actions); we use our own action_logger.
    """
    # Disable all OASIS loggers
    oasis_loggers = [
        "social.agent",
        "social.twitter", 
        "social.rec",
        "oasis.env",
        "table",
    ]
    
    for logger_name in oasis_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)  # Only log critical errors
        logger.handlers.clear()
        logger.propagate = False


def init_logging_for_simulation(simulation_dir: str):
    """
    Initialize logging configuration for simulation

    Args:
        simulation_dir: Simulation directory path
    """
    # Disable OASIS verbose logs
    disable_oasis_logging()

    # Re-install the max_tokens filter now that camel/oasis may have added
    # handlers to the root logger.
    _install_max_tokens_filter()

    # Clean up old log directory (if exists)
    old_log_dir = os.path.join(simulation_dir, "log")
    if os.path.exists(old_log_dir):
        import shutil
        shutil.rmtree(old_log_dir, ignore_errors=True)


from action_logger import SimulationLogManager, PlatformActionLogger

try:
    from camel.memories import MemoryRecord
    from camel.messages import FunctionCallingMessage
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    import oasis
    from oasis import (
        ActionType,
        LLMAction,
        ManualAction,
        generate_twitter_agent_graph,
        generate_reddit_agent_graph
    )
except ImportError as e:
    print(f"Error: Missing dependency {e}")
    print("Please install first: pip install oasis-ai camel-ai")
    sys.exit(1)


# Available Twitter actions (excluding INTERVIEW; INTERVIEW can only be manually triggered via ManualAction)
TWITTER_ACTIONS = [
    ActionType.CREATE_POST,
    ActionType.LIKE_POST,
    ActionType.REPOST,
    ActionType.FOLLOW,
    ActionType.DO_NOTHING,
    ActionType.QUOTE_POST,
]

# Available Reddit actions (excluding INTERVIEW; INTERVIEW can only be manually triggered via ManualAction)
REDDIT_ACTIONS = [
    ActionType.LIKE_POST,
    ActionType.DISLIKE_POST,
    ActionType.CREATE_POST,
    ActionType.CREATE_COMMENT,
    ActionType.LIKE_COMMENT,
    ActionType.DISLIKE_COMMENT,
    ActionType.SEARCH_POSTS,
    ActionType.SEARCH_USER,
    ActionType.TREND,
    ActionType.REFRESH,
    ActionType.DO_NOTHING,
    ActionType.FOLLOW,
    ActionType.MUTE,
]


def _archive_or_remove_db(db_path, log_fn=print):
    """Prepare a fresh simulation DB without destroying a prior run's data.

    OASIS needs a clean database file for a new run, but unconditionally deleting
    the old one loses everything a crashed/previous run recorded. Instead move it
    aside to a single .bak (kept for inspection/recovery), and fall back to
    removal only if the archive fails. Both operations tolerate a Windows file
    lock from an orphaned prior process rather than crashing at startup.
    """
    if not os.path.exists(db_path):
        return
    backup_path = db_path + ".bak"
    try:
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.replace(db_path, backup_path)
        return
    except OSError as e:
        log_fn(f"Could not archive previous DB ({e}); attempting removal")
    try:
        os.remove(db_path)
    except OSError as e:
        log_fn(f"Could not remove previous DB (still locked?): {e}")


def write_json_atomic(path: str, data: Dict[str, Any], attempts: int = 5) -> None:
    """Write JSON so a concurrent reader never sees a torn file.

    Writes a sibling temp file and os.replace()s it into place. On Windows the
    replace fails with PermissionError while the backend has the target open
    for reading, so retry briefly before giving up.
    """
    tmp_path = f"{path}.{os.getpid()}.tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    for attempt in range(attempts):
        try:
            os.replace(tmp_path, path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise
            time.sleep(0.05 * (attempt + 1))


# IPC related constants
IPC_COMMANDS_DIR = "ipc_commands"
IPC_RESPONSES_DIR = "ipc_responses"
ENV_STATUS_FILE = "env_status.json"

class CommandType:
    """Command type constants"""
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class ParallelIPCHandler:
    """
    Dual-platform IPC command handler

    Manages environments for both platforms, processes Interview commands
    """
    
    def __init__(
        self,
        simulation_dir: str,
        twitter_env=None,
        twitter_agent_graph=None,
        reddit_env=None,
        reddit_agent_graph=None
    ):
        self.simulation_dir = simulation_dir
        self.twitter_env = twitter_env
        self.twitter_agent_graph = twitter_agent_graph
        self.reddit_env = reddit_env
        self.reddit_agent_graph = reddit_agent_graph
        
        self.commands_dir = os.path.join(simulation_dir, IPC_COMMANDS_DIR)
        self.responses_dir = os.path.join(simulation_dir, IPC_RESPONSES_DIR)
        self.status_file = os.path.join(simulation_dir, ENV_STATUS_FILE)
        
        # Ensure directories exist
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
    
    def update_status(self, status: str):
        """Update environment status"""
        write_json_atomic(self.status_file, {
            "status": status,
            "twitter_available": self.twitter_env is not None,
            "reddit_available": self.reddit_env is not None,
            "timestamp": datetime.now().isoformat()
        })
    
    def poll_command(self) -> Optional[Dict[str, Any]]:
        """Poll for pending commands"""
        if not os.path.exists(self.commands_dir):
            return None
        
        # Get command files (sorted by time)
        command_files = []
        for filename in os.listdir(self.commands_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.commands_dir, filename)
                try:
                    command_files.append((filepath, os.path.getmtime(filepath)))
                except OSError:
                    # The file vanished between listdir and getmtime (e.g. the
                    # Flask side deleted a timed-out command). Skip it — this
                    # benign race must not propagate and tear down the sim.
                    continue

        command_files.sort(key=lambda x: x[1])
        
        for filepath, _ in command_files:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
        
        return None
    
    def send_response(self, command_id: str, status: str, result: Dict = None, error: str = None):
        """Send response"""
        response = {
            "command_id": command_id,
            "status": status,
            "result": result,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        write_json_atomic(response_file, response)
        
        # Delete command file
        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        try:
            os.remove(command_file)
        except OSError:
            pass
    
    def _get_env_and_graph(self, platform: str):
        """
        Get the environment and agent_graph for the specified platform

        Args:
            platform: Platform name ("twitter" or "reddit")

        Returns:
            (env, agent_graph, platform_name) or (None, None, None)
        """
        if platform == "twitter" and self.twitter_env:
            return self.twitter_env, self.twitter_agent_graph, "twitter"
        elif platform == "reddit" and self.reddit_env:
            return self.reddit_env, self.reddit_agent_graph, "reddit"
        else:
            return None, None, None
    
    async def _interview_single_platform(self, agent_id: int, prompt: str, platform: str) -> Dict[str, Any]:
        """
        Execute an interview on a single platform

        Returns:
            Dict containing results, or dict containing error
        """
        env, agent_graph, actual_platform = self._get_env_and_graph(platform)
        
        if not env or not agent_graph:
            return {"platform": platform, "error": f"{platform} platform not available"}
        
        try:
            agent = agent_graph.get_agent(agent_id)
            interview_action = ManualAction(
                action_type=ActionType.INTERVIEW,
                action_args={"prompt": prompt}
            )
            actions = {agent: interview_action}
            baseline_rowid = self._max_trace_rowid(actual_platform)
            await env.step(actions)

            result = self._get_interview_result(agent_id, actual_platform, after_rowid=baseline_rowid)
            result["platform"] = actual_platform
            if result.get("response") is None:
                return {"platform": actual_platform, "error": "No interview response recorded"}
            return result
            
        except Exception as e:
            return {"platform": platform, "error": str(e)}
    
    async def handle_interview(self, command_id: str, agent_id: int, prompt: str, platform: str = None) -> bool:
        """
        Handle a single agent interview command

        Args:
            command_id: Command ID
            agent_id: Agent ID
            prompt: Interview question
            platform: Specified platform (optional)
                - "twitter": Interview on Twitter platform only
                - "reddit": Interview on Reddit platform only
                - None/unspecified: Interview on both platforms simultaneously, return combined results

        Returns:
            True for success, False for failure
        """
        # If a specific platform is specified, only interview on that platform
        if platform in ("twitter", "reddit"):
            result = await self._interview_single_platform(agent_id, prompt, platform)
            
            if "error" in result:
                self.send_response(command_id, "failed", error=result["error"])
                print(f"  Interview failed: agent_id={agent_id}, platform={platform}, error={result['error']}")
                return False
            else:
                self.send_response(command_id, "completed", result=result)
                print(f"  Interview completed: agent_id={agent_id}, platform={platform}")
                return True
        
        # No platform specified: interview on both platforms simultaneously
        if not self.twitter_env and not self.reddit_env:
            self.send_response(command_id, "failed", error="No simulation environment available")
            return False
        
        results = {
            "agent_id": agent_id,
            "prompt": prompt,
            "platforms": {}
        }
        success_count = 0
        
        # Interview both platforms in parallel
        tasks = []
        platforms_to_interview = []
        
        if self.twitter_env:
            tasks.append(self._interview_single_platform(agent_id, prompt, "twitter"))
            platforms_to_interview.append("twitter")
        
        if self.reddit_env:
            tasks.append(self._interview_single_platform(agent_id, prompt, "reddit"))
            platforms_to_interview.append("reddit")
        
        # Execute in parallel
        platform_results = await asyncio.gather(*tasks)
        
        for platform_name, platform_result in zip(platforms_to_interview, platform_results):
            results["platforms"][platform_name] = platform_result
            if "error" not in platform_result:
                success_count += 1
        
        if success_count > 0:
            self.send_response(command_id, "completed", result=results)
            print(f"  Interview completed: agent_id={agent_id}, successful_platforms={success_count}/{len(platforms_to_interview)}")
            return True
        else:
            errors = [f"{p}: {r.get('error', 'unknown error')}" for p, r in results["platforms"].items()]
            self.send_response(command_id, "failed", error="; ".join(errors))
            print(f"  Interview failed: agent_id={agent_id}, all platforms failed")
            return False
    
    async def handle_batch_interview(self, command_id: str, interviews: List[Dict], platform: str = None) -> bool:
        """
        Handle batch interview command

        Args:
            command_id: Command ID
            interviews: [{"agent_id": int, "prompt": str, "platform": str(optional)}, ...]
            platform: Default platform (can be overridden per interview item)
                - "twitter": Interview on Twitter platform only
                - "reddit": Interview on Reddit platform only
                - None/unspecified: Interview each agent on both platforms
        """
        # Group by platform
        twitter_interviews = []
        reddit_interviews = []
        both_platforms_interviews = []  # Need to interview on both platforms
        
        for interview in interviews:
            item_platform = interview.get("platform", platform)
            if item_platform == "twitter":
                twitter_interviews.append(interview)
            elif item_platform == "reddit":
                reddit_interviews.append(interview)
            else:
                # No platform specified: interview on both platforms
                both_platforms_interviews.append(interview)
        
        # Split both_platforms_interviews into the two platforms
        if both_platforms_interviews:
            if self.twitter_env:
                twitter_interviews.extend(both_platforms_interviews)
            if self.reddit_env:
                reddit_interviews.extend(both_platforms_interviews)
        
        results = {}
        for platform_name, platform_interviews in (("twitter", twitter_interviews), ("reddit", reddit_interviews)):
            results.update(await self._batch_interview_platform(platform_name, platform_interviews))
        
        succeeded = sum(1 for r in results.values() if r.get("response") is not None)
        if succeeded:
            self.send_response(command_id, "completed", result={
                "interviews_count": len(results),
                "succeeded_count": succeeded,
                "results": results
            })
            print(f"  Batch interview completed: {succeeded}/{len(results)} agents answered")
            return True
        else:
            self.send_response(command_id, "failed", error="No successful interviews")
            return False

    async def _batch_interview_platform(self, platform: str, interviews: List[Dict]) -> Dict[str, Any]:
        """Interview several agents on one platform in a single env.step.

        Results only accept trace rows newer than the pre-step baseline, so an
        agent whose interview failed reports no response instead of returning
        its previous answer.
        """
        env, agent_graph, _ = self._get_env_and_graph(platform)
        if not interviews or not env:
            return {}
        results = {}
        try:
            actions = {}
            for interview in interviews:
                agent_id = interview.get("agent_id")
                try:
                    agent = agent_graph.get_agent(agent_id)
                except Exception as e:  # noqa: BLE001
                    print(f"  Warning: Cannot get {platform} Agent {agent_id}: {e}")
                    continue
                actions[agent] = ManualAction(
                    action_type=ActionType.INTERVIEW,
                    action_args={"prompt": interview.get("prompt", "")}
                )
            if not actions:
                return {}
            baseline_rowid = self._max_trace_rowid(platform)
            await env.step(actions)
            for interview in interviews:
                agent_id = interview.get("agent_id")
                result = self._get_interview_result(agent_id, platform, after_rowid=baseline_rowid)
                result["platform"] = platform
                if result.get("response") is None:
                    result["error"] = "No interview response recorded"
                results[f"{platform}_{agent_id}"] = result
        except Exception as e:  # noqa: BLE001
            print(f"  {platform} batch interview failed: {e}")
        return results
    
    def _max_trace_rowid(self, platform: str) -> int:
        """Return the current MAX(rowid) of the trace table (or 0).

        Captured before an interview step so _get_interview_result can require a
        trace NEWER than this baseline — otherwise a failed interview (which
        writes no trace) would return a previous interview's answer as if it were
        the current one.
        """
        db_path = os.path.join(self.simulation_dir, f"{platform}_simulation.db")
        if not os.path.exists(db_path):
            return 0
        try:
            conn = sqlite3.connect(db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(rowid) FROM trace")
                row = cursor.fetchone()
                return (row[0] or 0) if row else 0
            finally:
                conn.close()
        except Exception:
            return 0

    def _get_interview_result(self, agent_id: int, platform: str, after_rowid: Optional[int] = None) -> Dict[str, Any]:
        """Get the latest interview result from the database.

        When after_rowid is given, only a trace row newer than that baseline is
        accepted, so a stale prior answer is never returned as the current one.
        """
        db_path = os.path.join(self.simulation_dir, f"{platform}_simulation.db")

        result = {
            "agent_id": agent_id,
            "response": None,
            "timestamp": None
        }

        if not os.path.exists(db_path):
            return result

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Query the latest interview record (only fresh rows when a baseline
            # rowid is supplied, so a failed interview can't return stale data).
            if after_rowid is not None and after_rowid >= 0:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = ? AND user_id = ? AND rowid > ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (ActionType.INTERVIEW.value, agent_id, after_rowid))
            else:
                cursor.execute("""
                    SELECT user_id, info, created_at
                    FROM trace
                    WHERE action = ? AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (ActionType.INTERVIEW.value, agent_id))

            row = cursor.fetchone()
            if row:
                user_id, info_json, created_at = row
                try:
                    info = json.loads(info_json) if info_json else {}
                    result["response"] = info.get("response", info)
                    result["timestamp"] = created_at
                except json.JSONDecodeError:
                    result["response"] = info_json
            
            conn.close()
            
        except Exception as e:
            print(f"  Failed to read interview result: {e}")
        
        return result
    
    async def process_commands(self) -> Tuple[bool, bool]:
        """
        Process the next pending command

        Returns:
            (handled, should_continue): handled is True when a command was
            processed; should_continue is False when the env must shut down.
        """
        command = self.poll_command()
        if not command:
            return False, True
        
        command_id = command.get("command_id")
        command_type = command.get("command_type")
        args = command.get("args", {})
        
        print(f"\nReceived IPC command: {command_type}, id={command_id}")
        
        if command_type == CommandType.INTERVIEW:
            await self.handle_interview(
                command_id,
                args.get("agent_id", 0),
                args.get("prompt", ""),
                args.get("platform")
            )
            return True, True
            
        elif command_type == CommandType.BATCH_INTERVIEW:
            await self.handle_batch_interview(
                command_id,
                args.get("interviews", []),
                args.get("platform")
            )
            return True, True
            
        elif command_type == CommandType.CLOSE_ENV:
            print("Received close environment command")
            self.send_response(command_id, "completed", result={"message": "Environment shutting down"})
            return True, False
        
        else:
            self.send_response(command_id, "failed", error=f"Unknown command type: {command_type}")
            return True, True


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# Non-core action types to filter out (these actions have low analytical value)
FILTERED_ACTIONS = {'refresh', 'sign_up'}

# Action type mapping (database name -> standard name)
ACTION_TYPE_MAP = {
    'create_post': 'CREATE_POST',
    'like_post': 'LIKE_POST',
    'dislike_post': 'DISLIKE_POST',
    'repost': 'REPOST',
    'quote_post': 'QUOTE_POST',
    'follow': 'FOLLOW',
    'mute': 'MUTE',
    'create_comment': 'CREATE_COMMENT',
    'like_comment': 'LIKE_COMMENT',
    'dislike_comment': 'DISLIKE_COMMENT',
    'search_posts': 'SEARCH_POSTS',
    'search_user': 'SEARCH_USER',
    'trend': 'TREND',
    'do_nothing': 'DO_NOTHING',
    'interview': 'INTERVIEW',
}


def get_agent_names_from_config(config: Dict[str, Any]) -> Dict[int, str]:
    """
    Get agent_id -> entity_name mapping from simulation_config

    This allows actions.jsonl to display real entity names instead of generic "Agent_0" labels

    Args:
        config: Contents of simulation_config.json

    Returns:
        Dict mapping agent_id -> entity_name
    """
    agent_names = {}
    agent_configs = config.get("agent_configs", [])
    
    for agent_config in agent_configs:
        agent_id = agent_config.get("agent_id")
        entity_name = agent_config.get("entity_name", f"Agent_{agent_id}")
        if agent_id is not None:
            agent_names[agent_id] = entity_name
    
    return agent_names


def fetch_new_actions_from_db(
    db_path: str,
    last_rowid: int,
    agent_names: Dict[int, str]
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Fetch new action records from the database with enriched context information

    Args:
        db_path: Database file path
        last_rowid: Max rowid from last read (using rowid instead of created_at because different platforms use different created_at formats)
        agent_names: agent_id -> agent_name mapping

    Returns:
        (actions_list, new_last_rowid)
        - actions_list: List of actions, each containing agent_id, agent_name, action_type, action_args (with context)
        - new_last_rowid: New max rowid value
    """
    actions = []
    new_last_rowid = last_rowid
    
    if not os.path.exists(db_path):
        return actions, new_last_rowid

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Use rowid to track processed records (rowid is SQLite's built-in auto-increment field)
        # This avoids created_at format differences (Twitter uses integers, Reddit uses datetime strings)
        cursor.execute("""
            SELECT rowid, user_id, action, info
            FROM trace
            WHERE rowid > ?
            ORDER BY rowid ASC
        """, (last_rowid,))
        
        for rowid, user_id, action, info_json in cursor.fetchall():
            # Update max rowid
            new_last_rowid = rowid
            
            # Filter out non-core actions
            if action in FILTERED_ACTIONS:
                continue
            
            # Parse action arguments
            try:
                action_args = json.loads(info_json) if info_json else {}
            except json.JSONDecodeError:
                action_args = {}
            
            # Simplify action_args, keep only key fields (preserve full content, no truncation)
            simplified_args = {}
            if 'content' in action_args:
                simplified_args['content'] = action_args['content']
            if 'post_id' in action_args:
                simplified_args['post_id'] = action_args['post_id']
            if 'comment_id' in action_args:
                simplified_args['comment_id'] = action_args['comment_id']
            if 'quoted_id' in action_args:
                simplified_args['quoted_id'] = action_args['quoted_id']
            if 'new_post_id' in action_args:
                simplified_args['new_post_id'] = action_args['new_post_id']
            if 'follow_id' in action_args:
                simplified_args['follow_id'] = action_args['follow_id']
            if 'query' in action_args:
                simplified_args['query'] = action_args['query']
            if 'like_id' in action_args:
                simplified_args['like_id'] = action_args['like_id']
            if 'dislike_id' in action_args:
                simplified_args['dislike_id'] = action_args['dislike_id']
            
            # Convert action type name
            action_type = ACTION_TYPE_MAP.get(action, action.upper())
            
            # Enrich with context information (post content, usernames, etc.)
            _enrich_action_context(cursor, action_type, simplified_args, agent_names)
            
            actions.append({
                'agent_id': user_id,
                'agent_name': agent_names.get(user_id, f'Agent_{user_id}'),
                'action_type': action_type,
                'action_args': simplified_args,
            })
        
    except Exception as e:
        print(f"Failed to read database actions: {e}")
    finally:
        if conn is not None:
            conn.close()

    return actions, new_last_rowid


def _enrich_action_context(
    cursor,
    action_type: str,
    action_args: Dict[str, Any],
    agent_names: Dict[int, str]
) -> None:
    """
    Enrich actions with context information (post content, usernames, etc.)

    Args:
        cursor: Database cursor
        action_type: Action type
        action_args: Action arguments (will be modified in place)
        agent_names: agent_id -> agent_name mapping
    """
    try:
        # Like/dislike post: add post content and author
        if action_type in ('LIKE_POST', 'DISLIKE_POST'):
            post_id = action_args.get('post_id')
            if post_id:
                post_info = _get_post_info(cursor, post_id, agent_names)
                if post_info:
                    action_args['post_content'] = post_info.get('content', '')
                    action_args['post_author_name'] = post_info.get('author_name', '')
        
        # Repost: add original post content and author
        elif action_type == 'REPOST':
            new_post_id = action_args.get('new_post_id')
            if new_post_id:
                # The reposted post's original_post_id points to the original post
                cursor.execute("""
                    SELECT original_post_id FROM post WHERE post_id = ?
                """, (new_post_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    original_post_id = row[0]
                    original_info = _get_post_info(cursor, original_post_id, agent_names)
                    if original_info:
                        action_args['original_content'] = original_info.get('content', '')
                        action_args['original_author_name'] = original_info.get('author_name', '')
        
        # Quote post: add original post content, author, and quote comment
        elif action_type == 'QUOTE_POST':
            quoted_id = action_args.get('quoted_id')
            new_post_id = action_args.get('new_post_id')
            
            if quoted_id:
                original_info = _get_post_info(cursor, quoted_id, agent_names)
                if original_info:
                    action_args['original_content'] = original_info.get('content', '')
                    action_args['original_author_name'] = original_info.get('author_name', '')
            
            # Get the quote post's comment content (quote_content)
            if new_post_id:
                cursor.execute("""
                    SELECT quote_content FROM post WHERE post_id = ?
                """, (new_post_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    action_args['quote_content'] = row[0]
        
        # Follow user: add followed user's name
        elif action_type == 'FOLLOW':
            follow_id = action_args.get('follow_id')
            if follow_id:
                # Get followee_id from follow table
                cursor.execute("""
                    SELECT followee_id FROM follow WHERE follow_id = ?
                """, (follow_id,))
                row = cursor.fetchone()
                if row:
                    followee_id = row[0]
                    target_name = _get_user_name(cursor, followee_id, agent_names)
                    if target_name:
                        action_args['target_user_name'] = target_name
        
        # Mute user: add muted user's name
        elif action_type == 'MUTE':
            # Get user_id or target_id from action_args
            target_id = action_args.get('user_id') or action_args.get('target_id')
            if target_id:
                target_name = _get_user_name(cursor, target_id, agent_names)
                if target_name:
                    action_args['target_user_name'] = target_name
        
        # Like/dislike comment: add comment content and author
        elif action_type in ('LIKE_COMMENT', 'DISLIKE_COMMENT'):
            comment_id = action_args.get('comment_id')
            if comment_id:
                comment_info = _get_comment_info(cursor, comment_id, agent_names)
                if comment_info:
                    action_args['comment_content'] = comment_info.get('content', '')
                    action_args['comment_author_name'] = comment_info.get('author_name', '')
        
        # Create comment: add commented post information
        elif action_type == 'CREATE_COMMENT':
            post_id = action_args.get('post_id')
            if post_id:
                post_info = _get_post_info(cursor, post_id, agent_names)
                if post_info:
                    action_args['post_content'] = post_info.get('content', '')
                    action_args['post_author_name'] = post_info.get('author_name', '')
    
    except Exception as e:
        # Context enrichment failure does not affect the main flow
        print(f"Failed to enrich action context: {e}")


def _get_post_info(
    cursor,
    post_id: int,
    agent_names: Dict[int, str]
) -> Optional[Dict[str, str]]:
    """
    Get post information

    Args:
        cursor: Database cursor
        post_id: Post ID
        agent_names: agent_id -> agent_name mapping

    Returns:
        Dict containing content and author_name, or None
    """
    try:
        cursor.execute("""
            SELECT p.content, p.user_id, u.agent_id
            FROM post p
            LEFT JOIN user u ON p.user_id = u.user_id
            WHERE p.post_id = ?
        """, (post_id,))
        row = cursor.fetchone()
        if row:
            content = row[0] or ''
            user_id = row[1]
            agent_id = row[2]
            
            # Prefer names from agent_names
            author_name = ''
            if agent_id is not None and agent_id in agent_names:
                author_name = agent_names[agent_id]
            elif user_id:
                # Get name from user table
                cursor.execute("SELECT name, user_name FROM user WHERE user_id = ?", (user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    author_name = user_row[0] or user_row[1] or ''

            return {'content': content, 'author_name': author_name}
    except Exception:
        pass
    return None


def _get_user_name(
    cursor,
    user_id: int,
    agent_names: Dict[int, str]
) -> Optional[str]:
    """
    Get user name

    Args:
        cursor: Database cursor
        user_id: User ID
        agent_names: agent_id -> agent_name mapping

    Returns:
        User name, or None
    """
    try:
        cursor.execute("""
            SELECT agent_id, name, user_name FROM user WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            agent_id = row[0]
            name = row[1]
            user_name = row[2]
            
            # Prefer names from agent_names
            if agent_id is not None and agent_id in agent_names:
                return agent_names[agent_id]
            return name or user_name or ''
    except Exception:
        pass
    return None


def _get_comment_info(
    cursor,
    comment_id: int,
    agent_names: Dict[int, str]
) -> Optional[Dict[str, str]]:
    """
    Get comment information

    Args:
        cursor: Database cursor
        comment_id: Comment ID
        agent_names: agent_id -> agent_name mapping

    Returns:
        Dict containing content and author_name, or None
    """
    try:
        cursor.execute("""
            SELECT c.content, c.user_id, u.agent_id
            FROM comment c
            LEFT JOIN user u ON c.user_id = u.user_id
            WHERE c.comment_id = ?
        """, (comment_id,))
        row = cursor.fetchone()
        if row:
            content = row[0] or ''
            user_id = row[1]
            agent_id = row[2]
            
            # Prefer names from agent_names
            author_name = ''
            if agent_id is not None and agent_id in agent_names:
                author_name = agent_names[agent_id]
            elif user_id:
                # Get name from user table
                cursor.execute("SELECT name, user_name FROM user WHERE user_id = ?", (user_id,))
                user_row = cursor.fetchone()
                if user_row:
                    author_name = user_row[0] or user_row[1] or ''

            return {'content': content, 'author_name': author_name}
    except Exception:
        pass
    return None


def create_model(config: Dict[str, Any], use_boost: bool = False):
    """
    Create LLM model

    Supports dual LLM configuration for faster parallel simulation:
    - General config: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
    - Boost config (optional): LLM_BOOST_API_KEY, LLM_BOOST_BASE_URL, LLM_BOOST_MODEL_NAME

    When boost LLM is configured, parallel simulation can use different API providers
    for different platforms, increasing concurrency.

    Args:
        config: Simulation configuration dict
        use_boost: Whether to use the boost LLM configuration (if available)
    """
    # Check if boost configuration is available
    boost_api_key = os.environ.get("LLM_BOOST_API_KEY", "")
    boost_base_url = os.environ.get("LLM_BOOST_BASE_URL", "")
    boost_model = os.environ.get("LLM_BOOST_MODEL_NAME", "")
    has_boost_config = bool(boost_api_key)
    
    # Select which LLM to use based on parameters and configuration
    if use_boost and has_boost_config:
        # Use boost configuration
        llm_api_key = boost_api_key
        llm_base_url = boost_base_url
        llm_model = boost_model or os.environ.get("LLM_MODEL_NAME", "")
        config_label = "[Boost LLM]"
    else:
        # Swarm lane: SWARM_LLM_* with fallback to LLM_*. Keeps the OASIS
        # agents on a separate model from profile/config/report generation.
        swarm_model = os.environ.get("SWARM_LLM_MODEL_NAME", "")
        llm_api_key = os.environ.get("SWARM_LLM_API_KEY") or os.environ.get("LLM_API_KEY", "")
        llm_base_url = os.environ.get("SWARM_LLM_BASE_URL") or os.environ.get("LLM_BASE_URL", "")
        llm_model = swarm_model or os.environ.get("LLM_MODEL_NAME", "")
        config_label = "[Swarm LLM]" if swarm_model else "[General LLM]"
    
    # If no model name in .env, use config as fallback
    if not llm_model:
        llm_model = config.get("llm_model", "gpt-4o-mini")
    
    # Also set the env vars for any OASIS internals that read them directly.
    # NOTE: these are process-global and the two platforms create models
    # concurrently, so they race — which is exactly why the model credentials
    # below are ALSO passed explicitly to ModelFactory.create.
    if llm_api_key:
        os.environ["OPENAI_API_KEY"] = llm_api_key
    if llm_base_url:
        os.environ["OPENAI_API_BASE_URL"] = llm_base_url

    # Resolve the key for THIS model explicitly (lane key, else global fallback).
    api_key = llm_api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("Missing API Key configuration, please set LLM_API_KEY in the project root .env file")

    print(f"{config_label} model={llm_model}, base_url={llm_base_url[:40] if llm_base_url else 'default'}...")

    # Pass credentials directly so each platform's model is pinned to its own
    # lane regardless of the shared-env race, and a boost key is never paired
    # with a stale/empty base URL.
    create_kwargs = {
        "model_platform": ModelPlatformType.OPENAI,
        "model_type": llm_model,
        "api_key": api_key,
    }
    if llm_base_url:
        create_kwargs["url"] = llm_base_url
    return ModelFactory.create(**create_kwargs)


# Each OASIS agent keeps its whole chat history (every round's feed snapshot
# plus its own tool calls), and camel sends all of it on every call unless the
# agent's context has a token limit. The default limit is the model's context
# window (about 1M tokens for DeepSeek V4 Flash), so prompts, and cost, grew
# every round: a full 168-round run cost ~10x more in its second half than in
# its first. With a cap, camel drops the oldest turns first, keeps each tool
# call together with its result, and always keeps the persona's system prompt.
#
# The cap must only apply when the prompt is built, not when messages are
# stored. camel's ChatAgent.update_memory slices any message bigger than the
# budget left in the (already truncated) context, and once an agent is full
# that budget is ~0, so every feed snapshot was stored as thousands of
# one-token "[chunk n/N]" records. Agents then saw a garbled tail of their
# feed: in a measured run they commented 75% less and searched instead.
# Capped agents therefore store each message whole, shortened only if it alone
# would take more than half the cap.
#
# Users pick a level per run (--agent-memory). In a measured 168-round run,
# light cost ~90% less than no cap; agents stayed coherent but forgot more of
# the early week and repeated themselves more often.
AGENT_MEMORY_LEVELS = {"light": 12000, "medium": 24000, "heavy": None}
DEFAULT_SWARM_CONTEXT_TOKENS = AGENT_MEMORY_LEVELS["medium"]


def swarm_context_token_limit(agent_memory: Optional[str] = None) -> Optional[int]:
    """Per-agent context cap (None = no cap): the run's agent memory level if one
    was picked, else SWARM_CONTEXT_TOKEN_LIMIT (0 = no cap), else medium."""
    if agent_memory:
        return AGENT_MEMORY_LEVELS[agent_memory]
    raw = os.environ.get("SWARM_CONTEXT_TOKEN_LIMIT", "").strip()
    if not raw:
        return DEFAULT_SWARM_CONTEXT_TOKENS
    try:
        value = int(raw)
    except ValueError:
        print(f"Ignoring invalid SWARM_CONTEXT_TOKEN_LIMIT={raw!r}; using {DEFAULT_SWARM_CONTEXT_TOKENS}")
        return DEFAULT_SWARM_CONTEXT_TOKENS
    return value if value > 0 else None


def cap_agent_context(agent_graph, token_limit: Optional[int]) -> int:
    """Cap every agent's context at ``token_limit`` tokens; returns how many were capped."""
    if not token_limit:
        return 0
    capped = 0
    for _, agent in agent_graph.get_agents():
        memory = getattr(agent, "memory", None)
        creator = memory.get_context_creator() if hasattr(memory, "get_context_creator") else None
        # ScoreBasedContextCreator exposes token_limit read-only; the value it
        # truncates against is _token_limit.
        if creator is not None and hasattr(creator, "_token_limit"):
            creator._token_limit = token_limit
            agent.update_memory = _whole_message_memory_writer(
                agent, creator.token_counter, token_limit // 2)
            capped += 1
    return capped


def _whole_message_memory_writer(agent, token_counter, max_message_tokens: int):
    """Stand-in for camel's ChatAgent.update_memory that never slices a message."""
    def update_memory(message, role, timestamp: Optional[float] = None) -> None:
        agent.memory.write_record(MemoryRecord(
            message=shorten_message(message, token_counter, max_message_tokens),
            role_at_backend=role,
            timestamp=timestamp if timestamp is not None else time.time_ns() / 1_000_000_000,
            agent_id=agent.agent_id,
        ))
    return update_memory


def shorten_message(message, token_counter, max_tokens: int):
    """Keep the first ``max_tokens`` tokens of a message's text (a tool result's, if it has one)."""
    field = "result" if isinstance(message, FunctionCallingMessage) and isinstance(message.result, str) else "content"
    text = getattr(message, field)
    if not isinstance(text, str):
        return message
    token_ids = token_counter.encode(text)
    if len(token_ids) <= max_tokens:
        return message
    short = token_counter.decode(token_ids[:max_tokens]) + "\n[... cut to fit the agent's context limit]"
    return dataclasses.replace(message, **{field: short})


def get_active_agents_for_round(
    env,
    config: Dict[str, Any],
    current_hour: int,
    round_num: int
) -> List:
    """Determine which agents to activate this round based on time and configuration"""
    time_config = config.get("time_config", {})
    agent_configs = config.get("agent_configs", [])
    
    base_min = time_config.get("agents_per_hour_min", 5)
    base_max = time_config.get("agents_per_hour_max", 20)
    
    peak_hours = time_config.get("peak_hours", [9, 10, 11, 14, 15, 20, 21, 22])
    off_peak_hours = time_config.get("off_peak_hours", [0, 1, 2, 3, 4, 5])
    
    if current_hour in peak_hours:
        multiplier = time_config.get("peak_activity_multiplier", 1.5)
    elif current_hour in off_peak_hours:
        multiplier = time_config.get("off_peak_activity_multiplier", 0.3)
    else:
        multiplier = 1.0
    
    target_count = int(random.uniform(base_min, base_max) * multiplier)
    
    candidates = []
    for cfg in agent_configs:
        agent_id = cfg.get("agent_id", 0)
        active_hours = cfg.get("active_hours", list(range(8, 23)))
        activity_level = cfg.get("activity_level", 0.5)
        
        if current_hour not in active_hours:
            continue
        
        if random.random() < activity_level:
            candidates.append(agent_id)
    
    selected_ids = random.sample(
        candidates, 
        min(target_count, len(candidates))
    ) if candidates else []
    
    active_agents = []
    for agent_id in selected_ids:
        try:
            agent = env.agent_graph.get_agent(agent_id)
            active_agents.append((agent_id, agent))
        except Exception:
            pass
    
    return active_agents


class PlatformSimulation:
    """Platform simulation result container"""
    def __init__(self, platform: str = ""):
        self.platform = platform
        self.env = None
        self.agent_graph = None
        self.total_actions = 0
        self.rounds_completed = 0
        # "completed" | "stopped" | "failed"
        self.outcome = "failed"
        self.error: Optional[str] = None


# How many times a failed env.step is attempted before the run is aborted.
STEP_MAX_ATTEMPTS = max(1, int(os.environ.get("SIMSEND_STEP_MAX_ATTEMPTS", "3")))
STEP_RETRY_DELAY_SECONDS = float(os.environ.get("SIMSEND_STEP_RETRY_DELAY", "5"))

_PLATFORM_SETTINGS = {
    "twitter": {
        "label": "Twitter",
        "profile_file": "twitter_profiles.csv",  # OASIS Twitter uses CSV
        "db_file": "twitter_simulation.db",
        "use_boost": False,  # Twitter uses the general / swarm LLM lane
    },
    "reddit": {
        "label": "Reddit",
        "profile_file": "reddit_profiles.json",
        "db_file": "reddit_simulation.db",
        "use_boost": True,  # Reddit uses the boost LLM when configured
    },
}


def compute_total_rounds(config: Dict[str, Any], max_rounds: Optional[int] = None) -> int:
    time_config = config.get("time_config", {})
    total_hours = time_config.get("total_simulation_hours", 72)
    minutes_per_round = max(int(time_config.get("minutes_per_round", 30) or 30), 1)
    total_rounds = int(total_hours * 60) // minutes_per_round
    if max_rounds is not None and max_rounds > 0:
        total_rounds = min(total_rounds, max_rounds)
    return total_rounds


async def _step_with_retry(env, actions, log_info, what: str):
    """Run env.step, retrying transient failures. Re-raises the last error."""
    last_err = None
    for attempt in range(1, STEP_MAX_ATTEMPTS + 1):
        try:
            await env.step(actions)
            return
        except Exception as err:  # noqa: BLE001 - OASIS/LLM errors are untyped
            last_err = err
            if attempt < STEP_MAX_ATTEMPTS:
                delay = STEP_RETRY_DELAY_SECONDS * attempt
                log_info(f"env.step failed during {what} (attempt {attempt}/{STEP_MAX_ATTEMPTS}): "
                         f"{err}; retrying in {delay:.0f}s")
                await asyncio.sleep(delay)
    raise last_err


async def run_platform_simulation(
    platform: str,
    config: Dict[str, Any], 
    simulation_dir: str,
    action_logger: Optional[PlatformActionLogger] = None,
    main_logger: Optional[SimulationLogManager] = None,
    max_rounds: Optional[int] = None,
    agent_memory: Optional[str] = None
) -> PlatformSimulation:
    """Run one platform's simulation loop.

    Every exit path writes exactly one terminal event to the platform's
    actions.jsonl so the backend never has to guess:
      - simulation_end      every configured round ran
      - simulation_stopped  a shutdown signal interrupted the loop
      - simulation_failed   setup or a round failed after retries
    """
    settings = _PLATFORM_SETTINGS[platform]
    result = PlatformSimulation(platform)
    label = settings["label"]
    total_rounds = compute_total_rounds(config, max_rounds)
    total_actions = 0
    
    def log_info(msg):
        if main_logger:
            main_logger.info(f"[{label}] {msg}")
        print(f"[{label}] {msg}")
    
    def fail(error: str) -> PlatformSimulation:
        result.outcome = "failed"
        result.error = error
        result.total_actions = total_actions
        log_info(f"Simulation failed after {result.rounds_completed} rounds: {error}")
        if action_logger:
            action_logger.log_simulation_failed(result.rounds_completed, total_rounds, total_actions, error)
        return result
    
    try:
        log_info("Initializing...")
        model = create_model(config, use_boost=settings["use_boost"])
    
        profile_path = os.path.join(simulation_dir, settings["profile_file"])
        if not os.path.exists(profile_path):
            return fail(f"Profile file not found: {profile_path}")
    
        if platform == "twitter":
            result.agent_graph = await generate_twitter_agent_graph(
                profile_path=profile_path, model=model, available_actions=TWITTER_ACTIONS,
            )
            platform_type = oasis.DefaultPlatformType.TWITTER
        else:
            result.agent_graph = await generate_reddit_agent_graph(
                profile_path=profile_path, model=model, available_actions=REDDIT_ACTIONS,
            )
            platform_type = oasis.DefaultPlatformType.REDDIT

        context_limit = swarm_context_token_limit(agent_memory)
        capped = cap_agent_context(result.agent_graph, context_limit)
        memory_label = f"agent memory: {agent_memory}" if agent_memory else "SWARM_CONTEXT_TOKEN_LIMIT/default"
        if context_limit:
            log_info(f"Agent context capped at {context_limit} tokens ({capped} agents, {memory_label})")
        else:
            log_info(f"Agent context cap disabled ({memory_label})")

        # Real entity names instead of generic Agent_X labels
        agent_names = get_agent_names_from_config(config)
        for agent_id, agent in result.agent_graph.get_agents():
            if agent_id not in agent_names:
                agent_names[agent_id] = getattr(agent, 'name', f'Agent_{agent_id}')
    
        db_path = os.path.join(simulation_dir, settings["db_file"])
        _archive_or_remove_db(db_path, log_info)

        result.env = oasis.make(
            agent_graph=result.agent_graph,
            platform=platform_type,
            database_path=db_path,
            semaphore=30,  # Limit max concurrent LLM requests to prevent API overload
        )
        await result.env.reset()
        log_info("Environment started")
    except Exception as e:  # noqa: BLE001
        return fail(f"Setup failed: {e}")
    
    if action_logger:
        action_logger.log_simulation_start(config, total_rounds)
    
    last_rowid = 0  # Last processed trace rowid (rowid avoids created_at format differences)
    
    # Round 0: initial posts
    if action_logger:
        action_logger.log_round_start(0, 0)
    initial_action_count = 0
    initial_actions = {}
    for post in config.get("event_config", {}).get("initial_posts", []):
        agent_id = post.get("poster_agent_id", 0)
        content = post.get("content", "")
        try:
            agent = result.env.agent_graph.get_agent(agent_id)
        except Exception as e:  # noqa: BLE001
            log_info(f"Skipping initial post for unknown agent {agent_id}: {e}")
            continue
        action = ManualAction(action_type=ActionType.CREATE_POST, action_args={"content": content})
        # One agent may author several initial posts: keep them all.
        if agent in initial_actions:
            existing = initial_actions[agent]
            initial_actions[agent] = (existing if isinstance(existing, list) else [existing]) + [action]
        else:
            initial_actions[agent] = action
        if action_logger:
            action_logger.log_action(
                round_num=0,
                agent_id=agent_id,
                agent_name=agent_names.get(agent_id, f"Agent_{agent_id}"),
                action_type="CREATE_POST",
                action_args={"content": content}
            )
        total_actions += 1
        initial_action_count += 1
    
    if initial_actions:
        try:
            await _step_with_retry(result.env, initial_actions, log_info, "initial posts")
        except Exception as e:  # noqa: BLE001
            return fail(f"Initial posts failed: {e}")
        log_info(f"Published {initial_action_count} initial posts")
    if action_logger:
        action_logger.log_round_end(0, initial_action_count)
    
    # Main simulation loop
    minutes_per_round = max(int(config.get("time_config", {}).get("minutes_per_round", 30) or 30), 1)
    start_time = datetime.now()
    
    for round_num in range(total_rounds):
        if _shutdown_event and _shutdown_event.is_set():
            log_info(f"Received shutdown signal, stopping before round {round_num + 1}")
            result.outcome = "stopped"
            result.total_actions = total_actions
            if action_logger:
                action_logger.log_simulation_stopped(result.rounds_completed, total_rounds, total_actions)
            return result
        
        simulated_minutes = round_num * minutes_per_round
        simulated_hour = (simulated_minutes // 60) % 24
        simulated_day = simulated_minutes // (60 * 24) + 1
        
        active_agents = get_active_agents_for_round(result.env, config, simulated_hour, round_num)
        
        if action_logger:
            action_logger.log_round_start(round_num + 1, simulated_hour)
        
        round_action_count = 0
        if active_agents:
            actions = {agent: LLMAction() for _, agent in active_agents}
            try:
                await _step_with_retry(result.env, actions, log_info, f"round {round_num + 1}")
            except Exception as step_err:  # noqa: BLE001
                # Do NOT report a truncated run as complete: the backend must
                # see this as a failure rather than build a report on it.
                return fail(f"env.step failed at round {round_num + 1}: {step_err}")
        
            actual_actions, last_rowid = fetch_new_actions_from_db(db_path, last_rowid, agent_names)
            for action_data in actual_actions:
                if action_logger:
                    action_logger.log_action(
                        round_num=round_num + 1,
                        agent_id=action_data['agent_id'],
                        agent_name=action_data['agent_name'],
                        action_type=action_data['action_type'],
                        action_args=action_data['action_args']
                    )
                total_actions += 1
                round_action_count += 1
        
        if action_logger:
            action_logger.log_round_end(
                round_num + 1, round_action_count,
                simulated_hours=round((round_num + 1) * minutes_per_round / 60, 2),
            )
        result.rounds_completed = round_num + 1
        
        if (round_num + 1) % 20 == 0:
            progress = (round_num + 1) / total_rounds * 100
            log_info(f"Day {simulated_day}, {simulated_hour:02d}:00 - Round {round_num + 1}/{total_rounds} ({progress:.1f}%)")
    
    # Note: the environment stays open so it can serve interviews
    if action_logger:
        action_logger.log_simulation_end(total_rounds, total_actions)
    result.outcome = "completed"
    result.total_actions = total_actions
    elapsed = (datetime.now() - start_time).total_seconds()
    log_info(f"Simulation loop completed! Elapsed: {elapsed:.1f}s, total actions: {total_actions}")
    return result


async def run_twitter_simulation(config, simulation_dir, action_logger=None, main_logger=None, max_rounds=None):
    return await run_platform_simulation("twitter", config, simulation_dir, action_logger, main_logger, max_rounds)


async def run_reddit_simulation(config, simulation_dir, action_logger=None, main_logger=None, max_rounds=None):
    return await run_platform_simulation("reddit", config, simulation_dir, action_logger, main_logger, max_rounds)


EXIT_OK = 0
EXIT_FAILED = 1
EXIT_BAD_ARGS = 2
EXIT_STOPPED = 143  # 128 + SIGTERM: interrupted by a shutdown signal

# Seconds the finished environment waits for interview commands before it shuts
# itself down (0 disables the timeout). Keeps a completed simulation from holding
# a process, its DB handles and LLM clients forever.
INTERVIEW_IDLE_TIMEOUT = float(os.environ.get("SIMSEND_INTERVIEW_IDLE_TIMEOUT", "1800"))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='OASIS dual-platform parallel simulation')
    parser.add_argument(
        '--config', 
        type=str, 
        required=True,
        help='Configuration file path (simulation_config.json)'
    )
    platform_group = parser.add_mutually_exclusive_group()
    platform_group.add_argument(
        '--twitter-only',
        action='store_true',
        help='Run Twitter simulation only'
    )
    platform_group.add_argument(
        '--reddit-only',
        action='store_true',
        help='Run Reddit simulation only'
    )
    parser.add_argument(
        '--max-rounds',
        type=int,
        default=None,
        help='Maximum simulation rounds (optional, for truncating overly long simulations)'
    )
    parser.add_argument(
        '--agent-memory',
        choices=sorted(AGENT_MEMORY_LEVELS),
        default=None,
        help='How much of its own history each agent keeps: light (12k tokens), medium (24k), '
             'heavy (no cap). Default: SWARM_CONTEXT_TOKEN_LIMIT, else medium'
    )
    parser.add_argument(
        '--no-wait',
        action='store_true',
        default=False,
        help='Close environment immediately after simulation, do not enter command waiting mode'
    )
    return parser.parse_args(argv)
    

def summarize_exit_code(results: List[PlatformSimulation], shutdown_requested: bool) -> int:
    """Map platform outcomes to the process exit code the backend relies on."""
    if any(r.outcome == "failed" for r in results):
        return EXIT_FAILED
    if shutdown_requested or any(r.outcome == "stopped" for r in results):
        return EXIT_STOPPED
    return EXIT_OK


async def main(argv=None) -> int:
    args = parse_args(argv)
    
    # Create shutdown event at the start of main, ensuring the entire program can respond to shutdown signals
    global _shutdown_event
    _shutdown_event = asyncio.Event()
    
    if not os.path.exists(args.config):
        print(f"Error: Configuration file not found: {args.config}")
        return EXIT_BAD_ARGS
    
    config = load_config(args.config)
    simulation_dir = os.path.dirname(args.config) or "."
    wait_for_commands = not args.no_wait
    
    if args.twitter_only:
        platforms = ["twitter"]
    elif args.reddit_only:
        platforms = ["reddit"]
    else:
        platforms = ["twitter", "reddit"]

    # Initialize logging configuration (disable OASIS logs, clean up old files)
    init_logging_for_simulation(simulation_dir)
    
    log_manager = SimulationLogManager(simulation_dir)
    platform_loggers = {
        "twitter": log_manager.get_twitter_logger,
        "reddit": log_manager.get_reddit_logger,
    }
    
    total_rounds = compute_total_rounds(config, args.max_rounds)
    time_config = config.get("time_config", {})
    log_manager.info("=" * 60)
    log_manager.info(f"OASIS simulation ({' + '.join(platforms)})")
    log_manager.info(f"Config file: {args.config}")
    log_manager.info(f"Simulation ID: {config.get('simulation_id', 'unknown')}")
    log_manager.info(f"Command waiting mode: {'enabled' if wait_for_commands else 'disabled'}")
    log_manager.info(f"  - Total simulation duration: {time_config.get('total_simulation_hours', 72)} hours")
    log_manager.info(f"  - Time per round: {time_config.get('minutes_per_round', 30)} minutes")
    log_manager.info(f"  - Rounds to execute: {total_rounds}")
    log_manager.info(f"  - Agent count: {len(config.get('agent_configs', []))}")
    log_manager.info("=" * 60)
    
    start_time = datetime.now()
    
    # return_exceptions=True so one platform raising doesn't cancel the sibling.
    raw_results = await asyncio.gather(
        *(run_platform_simulation(p, config, simulation_dir, platform_loggers[p](), log_manager,
                                  args.max_rounds, args.agent_memory)
          for p in platforms),
        return_exceptions=True,
    )
    results: List[PlatformSimulation] = []
    for platform, res in zip(platforms, raw_results):
        if isinstance(res, BaseException):
            # run_platform_simulation logs its own failures; this is a bug path.
            log_manager.error(f"{platform} simulation crashed: {res}")
            crashed = PlatformSimulation(platform)
            crashed.error = str(res)
            platform_loggers[platform]().log_simulation_failed(0, total_rounds, 0, f"Crashed: {res}")
            res = crashed
        results.append(res)
    
    by_platform = {r.platform: r for r in results}
    total_elapsed = (datetime.now() - start_time).total_seconds()
    log_manager.info("=" * 60)
    for r in results:
        log_manager.info(f"[{r.platform}] outcome={r.outcome} rounds={r.rounds_completed}/{total_rounds} "
                         f"actions={r.total_actions}" + (f" error={r.error}" if r.error else ""))
    log_manager.info(f"Simulation loop finished. Total elapsed: {total_elapsed:.1f}s")
    
    exit_code = summarize_exit_code(results, _shutdown_event.is_set())
        
    # Only a fully successful run serves interviews; a failed or interrupted run
    # exits so the backend can report it.
    if wait_for_commands and exit_code == EXIT_OK:
        twitter_result = by_platform.get("twitter")
        reddit_result = by_platform.get("reddit")
        ipc_handler = ParallelIPCHandler(
            simulation_dir=simulation_dir,
            twitter_env=twitter_result.env if twitter_result else None,
            twitter_agent_graph=twitter_result.agent_graph if twitter_result else None,
            reddit_env=reddit_result.env if reddit_result else None,
            reddit_agent_graph=reddit_result.agent_graph if reddit_result else None
        )
        log_manager.info("Entering command waiting mode - environment stays running")
        log_manager.info("Supported commands: interview, batch_interview, close_env")
        if INTERVIEW_IDLE_TIMEOUT > 0:
            log_manager.info(f"Environment closes after {INTERVIEW_IDLE_TIMEOUT:.0f}s without commands")
        ipc_handler.update_status("alive")
        
        last_activity = time.monotonic()
        try:
            while not _shutdown_event.is_set():
                handled, should_continue = await ipc_handler.process_commands()
                if not should_continue:
                    break
                if handled:
                    last_activity = time.monotonic()
                elif INTERVIEW_IDLE_TIMEOUT > 0 and time.monotonic() - last_activity > INTERVIEW_IDLE_TIMEOUT:
                    log_manager.info("Interview idle timeout reached, closing environment")
                    break
                try:
                    await asyncio.wait_for(_shutdown_event.wait(), timeout=0.5)
                    break  # Received shutdown signal
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            print("\nTask cancelled")
        except Exception as e:  # noqa: BLE001
            log_manager.error(f"Command processing error: {e}")
        
        log_manager.info("Shutting down environment...")
        ipc_handler.update_status("stopped")
    
    for r in results:
        if r.env:
            try:
                await r.env.close()
                log_manager.info(f"[{r.platform}] Environment closed")
            except Exception as e:  # noqa: BLE001
                log_manager.warning(f"[{r.platform}] Failed to close environment: {e}")
    
    log_manager.info(f"All done (exit code {exit_code})")
    return exit_code


def setup_signal_handlers():
    """
    Set up signal handlers to ensure proper exit on SIGTERM/SIGINT

    The handler only sets a flag; the asyncio loop notices it, logs a
    simulation_stopped event, closes the environments and exits with
    EXIT_STOPPED. A second signal forces an immediate exit.
    """
    def signal_handler(signum, frame):
        global _cleanup_done
        sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        print(f"\nReceived {sig_name} signal, shutting down...")
        
        if not _cleanup_done:
            _cleanup_done = True
            if _shutdown_event:
                _shutdown_event.set()
        else:
            print("Force exiting...")
            os._exit(EXIT_STOPPED)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def run_cli(argv=None) -> int:
    setup_signal_handlers()
    exit_code = EXIT_FAILED
    try:
        exit_code = asyncio.run(main(argv))
    except KeyboardInterrupt:
        print("\nProgram interrupted")
        exit_code = EXIT_STOPPED
    finally:
        # Clean up multiprocessing resource tracker (prevent warnings on exit)
        try:
            from multiprocessing import resource_tracker
            resource_tracker._resource_tracker._stop()
        except Exception:
            pass
        print("Simulation process exited")
    return exit_code


if __name__ == "__main__":
    sys.exit(run_cli())
