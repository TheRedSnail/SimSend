"""
OASIS Reddit Simulation Script

Thin wrapper around run_parallel_simulation.py --reddit-only, so single-platform
runs share the same action logging, IPC handling, failure reporting and exit
codes as dual-platform runs.

Usage:
    python run_reddit_simulation.py --config simulation_config.json [--max-rounds N] [--no-wait]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_parallel_simulation  # noqa: E402


if __name__ == "__main__":
    sys.exit(run_parallel_simulation.run_cli(sys.argv[1:] + ["--reddit-only"]))
