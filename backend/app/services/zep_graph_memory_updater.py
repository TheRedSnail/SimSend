"""
Zep Graph Memory Update Service
Dynamically updates agent activities from simulations into the Zep graph
"""

import os
import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty, Full

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.retry import call_with_retry, is_transient_error

logger = get_logger('mirofish.zep_graph_memory_updater')


@dataclass
class AgentActivity:
    """Agent Activity Record"""
    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str

    def to_episode_text(self) -> str:
        """
        Convert the activity to a text description suitable for sending to Zep

        Uses natural language description format so Zep can extract entities and relationships.
        No simulation-related prefix is added to avoid misleading graph updates.
        """
        # Generate different descriptions based on action type
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }

        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()

        # Return "agent_name: activity_description" format directly, without simulation prefix
        return f"{self.agent_name}: {description}"

    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"published a post: \"{content}\""
        return "published a post"

    def _describe_like_post(self) -> str:
        """Like post - includes original post content and author info"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")

        if post_content and post_author:
            return f"liked {post_author}'s post: \"{post_content}\""
        elif post_content:
            return f"liked a post: \"{post_content}\""
        elif post_author:
            return f"liked a post by {post_author}"
        return "liked a post"

    def _describe_dislike_post(self) -> str:
        """Dislike post - includes original post content and author info"""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")

        if post_content and post_author:
            return f"disliked {post_author}'s post: \"{post_content}\""
        elif post_content:
            return f"disliked a post: \"{post_content}\""
        elif post_author:
            return f"disliked a post by {post_author}"
        return "disliked a post"

    def _describe_repost(self) -> str:
        """Repost - includes original post content and author info"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")

        if original_content and original_author:
            return f"reposted {original_author}'s post: \"{original_content}\""
        elif original_content:
            return f"reposted a post: \"{original_content}\""
        elif original_author:
            return f"reposted a post by {original_author}"
        return "reposted a post"

    def _describe_quote_post(self) -> str:
        """Quote post - includes original post content, author info, and quote comment"""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")

        base = ""
        if original_content and original_author:
            base = f"quoted {original_author}'s post \"{original_content}\""
        elif original_content:
            base = f"quoted a post \"{original_content}\""
        elif original_author:
            base = f"quoted a post by {original_author}"
        else:
            base = "quoted a post"

        if quote_content:
            base += f", commenting: \"{quote_content}\""
        return base

    def _describe_follow(self) -> str:
        """Follow user - includes the followed user's name"""
        target_user_name = self.action_args.get("target_user_name", "")

        if target_user_name:
            return f"followed user \"{target_user_name}\""
        return "followed a user"

    def _describe_create_comment(self) -> str:
        """Create comment - includes comment content and the commented post info"""
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")

        if content:
            if post_content and post_author:
                return f"commented on {post_author}'s post \"{post_content}\": \"{content}\""
            elif post_content:
                return f"commented on post \"{post_content}\": \"{content}\""
            elif post_author:
                return f"commented on {post_author}'s post: \"{content}\""
            return f"commented: \"{content}\""
        return "posted a comment"

    def _describe_like_comment(self) -> str:
        """Like comment - includes comment content and author info"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")

        if comment_content and comment_author:
            return f"liked {comment_author}'s comment: \"{comment_content}\""
        elif comment_content:
            return f"liked a comment: \"{comment_content}\""
        elif comment_author:
            return f"liked a comment by {comment_author}"
        return "liked a comment"

    def _describe_dislike_comment(self) -> str:
        """Dislike comment - includes comment content and author info"""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")

        if comment_content and comment_author:
            return f"disliked {comment_author}'s comment: \"{comment_content}\""
        elif comment_content:
            return f"disliked a comment: \"{comment_content}\""
        elif comment_author:
            return f"disliked a comment by {comment_author}"
        return "disliked a comment"

    def _describe_search(self) -> str:
        """Search posts - includes search keywords"""
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"searched for \"{query}\"" if query else "performed a search"

    def _describe_search_user(self) -> str:
        """Search user - includes search keywords"""
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"searched for user \"{query}\"" if query else "searched for a user"

    def _describe_mute(self) -> str:
        """Mute user - includes the muted user's name"""
        target_user_name = self.action_args.get("target_user_name", "")

        if target_user_name:
            return f"muted user \"{target_user_name}\""
        return "muted a user"

    def _describe_generic(self) -> str:
        # For unknown action types, generate a generic description
        return f"performed a {self.action_type} action"


class ZepGraphMemoryUpdater:
    """
    Zep Graph Memory Updater

    Monitors the simulation's actions log file and updates new agent activities
    to the Zep graph in real-time.
    Groups activities by platform and sends them in batches after accumulating BATCH_SIZE entries.

    All meaningful actions are updated to Zep. action_args contains complete context information:
    - Original post content for likes/dislikes
    - Original post content for reposts/quotes
    - Username for follows/mutes
    - Original comment content for comment likes/dislikes
    """

    # Batch send size (number of activities to accumulate per platform before sending)
    BATCH_SIZE = 5

    # Platform display name mapping (for console display)
    PLATFORM_DISPLAY_NAMES = {
        'twitter': 'World 1',
        'reddit': 'World 2',
    }

    # Send interval in seconds (to avoid sending too quickly)
    SEND_INTERVAL = 0.5

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    # Backpressure / shutdown limits (env-overridable)
    MAX_QUEUE_SIZE = int(os.environ.get("SIMSEND_ZEP_QUEUE_MAX", "5000"))
    FLUSH_TIMEOUT = float(os.environ.get("SIMSEND_ZEP_FLUSH_TIMEOUT", "30"))
    FLUSH_CHUNK_SIZE = 20  # activities per episode when flushing a backlog

    def __init__(self, graph_id: str, api_key: Optional[str] = None):
        """
        Initialize the updater

        Args:
            graph_id: Zep graph ID
            api_key: Zep API Key (optional, defaults to config value)
        """
        self.graph_id = graph_id
        self.api_key = api_key or Config.ZEP_API_KEY

        if not self.api_key:
            raise ValueError("ZEP_API_KEY is not configured")

        self.client = Zep(api_key=self.api_key)

        # Activity queue. Bounded: the producer (log monitor) is much faster
        # than Zep ingestion, so an unbounded queue grows without limit on a
        # big simulation. When full, the oldest pending activity is dropped.
        self._activity_queue: Queue = Queue(maxsize=self.MAX_QUEUE_SIZE)

        # Per-platform activity buffers (each platform accumulates to BATCH_SIZE before batch sending)
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            'twitter': [],
            'reddit': [],
        }
        self._buffer_lock = threading.Lock()

        # Control flags
        self._running = False
        self._drain_deadline: Optional[float] = None
        self._worker_thread: Optional[threading.Thread] = None

        # Statistics
        self._total_activities = 0  # Total activities added to queue
        self._total_sent = 0        # Successfully sent batch count
        self._total_items_sent = 0  # Successfully sent activity count
        self._failed_count = 0      # Failed batch count
        self._skipped_count = 0     # Filtered/skipped activity count (DO_NOTHING)
        self._dropped_count = 0     # Activities dropped (queue overflow or flush timeout)

        logger.info(f"ZepGraphMemoryUpdater initialized: graph_id={graph_id}, batch_size={self.BATCH_SIZE}")

    def _get_platform_display_name(self, platform: str) -> str:
        """Get platform display name"""
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)

    def start(self):
        """Start background worker thread"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"ZepMemoryUpdater-{self.graph_id[:8]}"
        )
        self._worker_thread.start()
        logger.info(f"ZepGraphMemoryUpdater started: graph_id={self.graph_id}")

    def stop(self, flush_timeout: Optional[float] = None):
        """Stop the worker and flush what is pending, within ``flush_timeout`` seconds.

        Whatever cannot be sent before the deadline is dropped (and counted)
        rather than blocking the caller indefinitely.
        """
        timeout = self.FLUSH_TIMEOUT if flush_timeout is None else flush_timeout
        deadline = time.monotonic() + timeout
        self._drain_deadline = deadline
        self._running = False

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=max(0.0, deadline - time.monotonic()) + 1)

        self._flush_remaining(deadline)

        logger.info(f"ZepGraphMemoryUpdater stopped: graph_id={self.graph_id}, "
                   f"total_activities={self._total_activities}, "
                   f"batches_sent={self._total_sent}, "
                   f"items_sent={self._total_items_sent}, "
                   f"failed={self._failed_count}, "
                   f"skipped={self._skipped_count}, "
                   f"dropped={self._dropped_count}")

    def add_activity(self, activity: AgentActivity):
        """
        Add an agent activity to the queue

        All meaningful actions are added to the queue, including:
        - CREATE_POST (create post)
        - CREATE_COMMENT (create comment)
        - QUOTE_POST (quote post)
        - SEARCH_POSTS (search posts)
        - SEARCH_USER (search user)
        - LIKE_POST/DISLIKE_POST (like/dislike post)
        - REPOST (repost)
        - FOLLOW (follow)
        - MUTE (mute)
        - LIKE_COMMENT/DISLIKE_COMMENT (like/dislike comment)

        action_args contains complete context information (e.g., original post text, usernames, etc.).

        Args:
            activity: Agent activity record
        """
        # Skip DO_NOTHING type activities
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return

        while True:
            try:
                self._activity_queue.put_nowait(activity)
                break
            except Full:
                try:
                    self._activity_queue.get_nowait()  # drop the oldest
                except Empty:
                    continue
                self._dropped_count += 1
                if self._dropped_count == 1 or self._dropped_count % 100 == 0:
                    logger.warning(
                        f"Zep activity queue full ({self.MAX_QUEUE_SIZE}); dropped "
                        f"{self._dropped_count} oldest activities so far (graph={self.graph_id})"
                    )
        self._total_activities += 1
        logger.debug(f"Added activity to Zep queue: {activity.agent_name} - {activity.action_type}")

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        """
        Add activity from dictionary data

        Args:
            data: Dictionary data parsed from actions.jsonl
            platform: Platform name (twitter/reddit)
        """
        # Skip event-type entries
        if "event_type" in data:
            return

        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )

        self.add_activity(activity)

    def _draining(self) -> bool:
        """After stop(): keep draining the queue until the flush deadline."""
        return (not self._running and self._drain_deadline is not None
                and time.monotonic() < self._drain_deadline
                and not self._activity_queue.empty())

    def _worker_loop(self):
        """Background worker loop - sends activities to Zep in batches by platform"""
        while self._running or self._draining():
            try:
                try:
                    activity = self._activity_queue.get(timeout=1)
                except Empty:
                    continue

                platform = activity.platform.lower()
                batch_size = self.BATCH_SIZE if self._running else self.FLUSH_CHUNK_SIZE
                batch = None
                with self._buffer_lock:
                    buffer = self._platform_buffers.setdefault(platform, [])
                    buffer.append(activity)
                    # Extract the batch under the lock, send it outside.
                    if len(buffer) >= batch_size:
                        batch = buffer[:batch_size]
                        self._platform_buffers[platform] = buffer[batch_size:]

                if batch:
                    self._send_batch_activities(batch, platform)
                    if self._running:
                        time.sleep(self.SEND_INTERVAL)

            except Exception as e:
                logger.error(f"Worker loop exception: {e}")
                time.sleep(1)

    def _send_batch_activities(self, activities: List[AgentActivity], platform: str) -> bool:
        """
        Batch send activities to Zep graph (merged into a single text)

        Args:
            activities: List of agent activities
            platform: Platform name

        Returns:
            True when the batch was accepted by Zep
        """
        if not activities:
            return True

        # Merge multiple activities into a single text, separated by newlines
        combined_text = "\n".join(activity.to_episode_text() for activity in activities)

        try:
            call_with_retry(
                self.client.graph.add,
                graph_id=self.graph_id,
                type="text",
                data=combined_text,
                max_retries=self.MAX_RETRIES - 1,
                initial_delay=self.RETRY_DELAY,
                retry_if=is_transient_error,
                description="Zep batch send",
            )
        except Exception as e:
            logger.error(f"Batch send to Zep failed ({len(activities)} activities): {e}")
            self._failed_count += 1
            return False

        self._total_sent += 1
        self._total_items_sent += len(activities)
        display_name = self._get_platform_display_name(platform)
        logger.info(f"Successfully batch sent {len(activities)} {display_name} activities to graph {self.graph_id}")
        logger.debug(f"Batch content preview: {combined_text[:200]}...")
        return True

    def _flush_remaining(self, deadline: Optional[float] = None):
        """Send what is left in the queue and buffers, in bounded chunks, until ``deadline``."""
        deadline = deadline if deadline is not None else time.monotonic() + self.FLUSH_TIMEOUT

        # Take everything out under the lock, send it without holding the lock.
        with self._buffer_lock:
            pending: Dict[str, List[AgentActivity]] = {
                platform: list(buffer) for platform, buffer in self._platform_buffers.items()
            }
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []
        while True:
            try:
                activity = self._activity_queue.get_nowait()
            except Empty:
                break
            pending.setdefault(activity.platform.lower(), []).append(activity)

        for platform, items in pending.items():
            if items:
                logger.info(f"Sending remaining {len(items)} {self._get_platform_display_name(platform)} activities")
            # Chunked: one giant episode can exceed Zep's size limit and then
            # fails (and is lost) as a whole.
            for start in range(0, len(items), self.FLUSH_CHUNK_SIZE):
                if time.monotonic() >= deadline:
                    left = len(items) - start
                    self._dropped_count += left
                    logger.warning(
                        f"Zep flush timed out; dropped {left} {platform} activities (graph={self.graph_id})"
                    )
                    break
                self._send_batch_activities(items[start:start + self.FLUSH_CHUNK_SIZE], platform)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}

        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,  # Total activities added to queue
            "batches_sent": self._total_sent,            # Successfully sent batch count
            "items_sent": self._total_items_sent,        # Successfully sent activity count
            "failed_count": self._failed_count,          # Failed batch count
            "skipped_count": self._skipped_count,        # Filtered/skipped activity count (DO_NOTHING)
            "dropped_count": self._dropped_count,        # Dropped (queue overflow / flush timeout)
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,                # Per-platform buffer sizes
            "running": self._running,
        }


class ZepGraphMemoryManager:
    """
    Manager for multiple simulations' Zep graph memory updaters

    Each simulation can have its own updater instance
    """

    _updaters: Dict[str, ZepGraphMemoryUpdater] = {}
    _lock = threading.Lock()

    @classmethod
    def create_updater(cls, simulation_id: str, graph_id: str) -> ZepGraphMemoryUpdater:
        """
        Create a graph memory updater for a simulation

        Args:
            simulation_id: Simulation ID
            graph_id: Zep graph ID

        Returns:
            ZepGraphMemoryUpdater instance
        """
        with cls._lock:
            # If one already exists, retire it (its flush runs in the background)
            old = cls._updaters.pop(simulation_id, None)
            if old is not None:
                threading.Thread(target=old.stop, daemon=True,
                                 name=f"ZepFlush-{simulation_id}").start()

            updater = ZepGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater

            logger.info(f"Created graph memory updater: simulation_id={simulation_id}, graph_id={graph_id}")
            return updater

    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[ZepGraphMemoryUpdater]:
        """Get the updater for a simulation"""
        return cls._updaters.get(simulation_id)

    @classmethod
    def stop_updater(cls, simulation_id: str, wait: bool = True):
        """Stop and remove a simulation's updater.

        With wait=False the bounded flush runs on a background thread, so an
        HTTP request (e.g. /stop) isn't held up by Zep ingestion.
        """
        with cls._lock:
            updater = cls._updaters.pop(simulation_id, None)
        if updater is None:
            return
        if wait:
            updater.stop()
        else:
            threading.Thread(
                target=updater.stop, daemon=True, name=f"ZepFlush-{simulation_id}"
            ).start()
        logger.info(f"Stopped graph memory updater: simulation_id={simulation_id}")

    # Flag to prevent stop_all from being called multiple times
    _stop_all_done = False

    @classmethod
    def stop_all(cls):
        """Stop all updaters"""
        # Prevent duplicate calls
        if cls._stop_all_done:
            return
        cls._stop_all_done = True

        with cls._lock:
            updaters = list(cls._updaters.items())
            cls._updaters.clear()

        # Flush in parallel so N simulations don't cost N x FLUSH_TIMEOUT at shutdown.
        def stop_one(simulation_id, updater):
            try:
                updater.stop()
            except Exception as e:
                logger.error(f"Failed to stop updater: simulation_id={simulation_id}, error={e}")

        threads = [threading.Thread(target=stop_one, args=item, daemon=True) for item in updaters]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=ZepGraphMemoryUpdater.FLUSH_TIMEOUT + 5)
        logger.info("All graph memory updaters stopped")

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all updaters"""
        with cls._lock:
            updaters = list(cls._updaters.items())
        return {sim_id: updater.get_stats() for sim_id, updater in updaters}
