"""CLI entry point for the Mars greenhouse agent mission runner.

Usage:
    uv run mars-agent [options]
    uv run python -m src.runner [options]
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .config import SIM_BASE_URL, VALID_DIFFICULTIES


def main() -> None:
    """Main entry point for the mission runner CLI."""
    parser = argparse.ArgumentParser(
        description="Mars Greenhouse Agent — autonomous greenhouse controller"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for simulation reset (default: 0)",
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        default="normal",
        choices=VALID_DIFFICULTIES,  # [C-6] validated against Difficulty str enum
        help="Simulation difficulty: easy, normal, or hard (default: normal)",
    )
    parser.add_argument(
        "--sim-url",
        type=str,
        default=SIM_BASE_URL,
        help=f"Simulation API base URL (default: {SIM_BASE_URL})",
    )
    parser.add_argument(
        "--sols",
        type=int,
        default=450,
        help="Number of sols to run (default: 450; use smaller for testing)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        default=False,
        help=(
            "Disable AgentCore Memory and use legacy file-based cross-session learning. "
            "Useful for local testing without AWS credentials. "
            "Clears BEDROCK_AGENTCORE_MEMORY_ID before loading orchestrator."
        ),
    )

    args = parser.parse_args()

    # Apply --no-memory before importing orchestrator (config is read at import time)
    if args.no_memory:
        os.environ.pop("BEDROCK_AGENTCORE_MEMORY_ID", None)

    # Configure logging with sol numbers in format
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    if args.no_memory:
        logger.info(
            "--no-memory flag set: using legacy file-based cross-session learning."
        )

    # Lazy import to avoid loading torch/strands at import time
    from .agents.orchestrator import run_mission

    client_url = args.sim_url
    from .sim_client import SimClient

    client = SimClient(client_url)

    logger.info(
        "Starting Mars Greenhouse Mission: seed=%d, difficulty=%s, sols=%d",
        args.seed,
        args.difficulty,
        args.sols,
    )

    try:
        result = run_mission(
            client,
            seed=args.seed,
            difficulty=args.difficulty,
            mission_sols=args.sols,
        )

        print("\n" + "=" * 60)
        print("MISSION COMPLETE")
        print("=" * 60)
        print(f"Run ID:        {result['run_id']}")
        print(f"Final Score:   {result['final_score']:.2f}")
        print(f"Mission Phase: {result['mission_phase']}")
        print(f"Total Crises:  {result['total_crises']}")
        print("=" * 60)

    except KeyboardInterrupt:
        logger.info("Mission interrupted by user. Fetching current score...")
        try:
            current = client.get_score_current()
            score = current.get("scores", {}).get("overall_score", 0.0)
            print(f"\nInterrupted. Current score: {score:.2f}")
        except Exception:
            print("\nInterrupted. Could not fetch current score.")
        sys.exit(0)


if __name__ == "__main__":
    main()
