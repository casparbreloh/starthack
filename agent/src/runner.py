"""CLI entry point for the Mars greenhouse agent mission runner.

Usage:
    uv run mars-agent [options]
    uv run python -m src.runner [options]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .config import SIM_BASE_URL, SIM_WS_URL, VALID_DIFFICULTIES
from .sim_client import SimClient


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
        "--ws",
        action="store_true",
        help="Use WebSocket mode instead of REST polling",
    )
    parser.add_argument(
        "--ws-url",
        type=str,
        default=SIM_WS_URL,
        help=f"Simulation WebSocket URL (default: {SIM_WS_URL})",
    )

    args = parser.parse_args()

    # Configure logging with sol numbers in format
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    if args.ws:
        # WebSocket mode
        from .agents.orchestrator import run_mission_ws

        logger.info(
            "Starting Mars Greenhouse Mission (WebSocket): "
            "seed=%d, difficulty=%s, sols=%d, ws_url=%s",
            args.seed,
            args.difficulty,
            args.sols,
            args.ws_url,
        )

        try:
            result = asyncio.run(
                run_mission_ws(
                    ws_url=args.ws_url,
                    seed=args.seed,
                    difficulty=args.difficulty,
                    mission_sols=args.sols,
                )
            )

            print("\n" + "=" * 60)
            print("MISSION COMPLETE (WebSocket)")
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

    else:
        # REST mode (original)
        from .agents.orchestrator import run_mission

        client = SimClient(args.sim_url)

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
