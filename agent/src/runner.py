"""CLI entry point for the Mars greenhouse agent mission runner.

Usage:
    uv run mars-agent [options]
    uv run python -m src.runner [options]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from .config import SIM_WS_URL, VALID_DIFFICULTIES


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
        choices=VALID_DIFFICULTIES,
        help="Simulation difficulty: easy, normal, or hard (default: normal)",
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
        "--ws-url",
        type=str,
        default=SIM_WS_URL,
        help=f"Simulation WebSocket URL (default: {SIM_WS_URL})",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Join an existing session instead of creating a new one",
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

    if args.no_memory:
        os.environ.pop("BEDROCK_AGENTCORE_MEMORY_ID", None)
        from . import config as _cfg

        _cfg.MEMORY_ID = ""
        _cfg.memory_enabled = False

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

    try:
        if args.session_id:
            from .agents.orchestrator import join_mission

            logger.info(
                "Joining session %s at %s",
                args.session_id,
                args.ws_url,
            )
            result = asyncio.run(
                join_mission(ws_url=args.ws_url, session_id=args.session_id)
            )
        else:
            from .agents.orchestrator import run_mission

            logger.info(
                "Starting Mars Greenhouse Mission: seed=%d, difficulty=%s, sols=%d, ws_url=%s",
                args.seed,
                args.difficulty,
                args.sols,
                args.ws_url,
            )
            result = asyncio.run(
                run_mission(
                    ws_url=args.ws_url,
                    seed=args.seed,
                    difficulty=args.difficulty,
                    mission_sols=args.sols,
                )
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
        logger.info("Mission interrupted by user.")
        print("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
