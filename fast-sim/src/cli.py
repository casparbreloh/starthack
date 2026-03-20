"""
CLI entry points for fast-sim.

Commands:
  run-local     -- run a single simulation locally with DEFAULT_STRATEGY
  local-sweep   -- run N simulations locally (sequential or parallel), print top-10
  dispatch      -- trigger SQS dispatch (invokes dispatcher Lambda)
  query         -- query results from S3/DynamoDB
  aggregate     -- manually trigger aggregation for a wave
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any


def _build_scenario(args: argparse.Namespace) -> "ScenarioConfig":
    """Build ScenarioConfig from CLI args."""
    from src.config import CrisisInjection, ScenarioConfig  # noqa: PLC0415

    import random as _rng  # noqa: PLC0415

    level = getattr(args, "scenario", 3)
    seed = getattr(args, "seed", 42)
    rng = _rng.Random(seed)

    if level == 0:
        return ScenarioConfig(level=0, injections=[])

    if level == 3:
        return ScenarioConfig(level=3, injections=[])

    # Levels 1-2: generate random crisis injections
    scenarios = ["water_leak", "dust_storm", "hvac_failure", "pathogen", "energy_disruption"]
    n_crises = 1 if level == 1 else rng.randint(2, 3)
    chosen = rng.sample(scenarios, k=min(n_crises, len(scenarios)))
    injections = []
    for sc in chosen:
        sol = rng.randint(30, 350)  # avoid very early/late
        kwargs: dict = {}
        if sc == "pathogen":
            kwargs["crop_id"] = None  # engine picks first active crop
        injections.append(CrisisInjection(sol=sol, scenario=sc, kwargs=kwargs))

    return ScenarioConfig(level=level, injections=sorted(injections, key=lambda i: i.sol))


def _run_local(args: argparse.Namespace) -> None:
    """Run a single simulation locally with DEFAULT_STRATEGY."""
    from copy import deepcopy  # noqa: PLC0415

    from src.config import DEFAULT_STRATEGY, RunConfig  # noqa: PLC0415
    from src.runner import run_simulation  # noqa: PLC0415

    strategy = deepcopy(DEFAULT_STRATEGY)
    strategy.scenario = _build_scenario(args)

    config = RunConfig(
        strategy=strategy,
        seed=getattr(args, "seed", 42),
        difficulty=getattr(args, "difficulty", "normal"),
        run_id="local-run-001",
        wave_id="local",
    )

    print(f"Running simulation (seed={config.seed}, difficulty={config.difficulty})...")
    start = time.monotonic()
    result = run_simulation(config)
    elapsed = time.monotonic() - start

    print("\n=== Simulation Result ===")
    print(f"  run_id:          {result.run_id}")
    print(f"  mission_outcome: {result.mission_outcome}")
    print(f"  final_sol:       {result.final_sol}/450")
    print(f"  final_score:     {result.final_score}/100")
    print(f"  survival:        {result.survival_score}/100")
    print(f"  nutrition:       {result.nutrition_score}/100")
    print(f"  efficiency:      {result.resource_efficiency_score}/100")
    print(f"  crisis_mgmt:     {result.crisis_mgmt_score}/100")
    print(f"  crops_planted:   {result.crops_planted}")
    print(f"  crops_harvested: {result.crops_harvested}")
    enc = result.crises_encountered
    res = result.crises_resolved
    print(f"  crises:          {enc} encountered, {res} resolved")
    print(f"  crop_yields:     {result.crop_yields}")
    print(f"  duration:        {result.duration_seconds:.2f}s (wall: {elapsed:.2f}s)")


def _local_sweep(args: argparse.Namespace) -> None:
    """Run N simulations locally, print results sorted by score."""
    import multiprocessing as mp  # noqa: PLC0415

    from src.runner import run_simulation  # noqa: PLC0415
    from src.sweep import generate_random_configs  # noqa: PLC0415

    n_runs = getattr(args, "n_runs", 10)
    n_parallel = getattr(args, "parallel", 1)
    scenario_level = getattr(args, "scenario", 3)

    print(f"Generating {n_runs} configs (scenario level {scenario_level})...")
    configs = generate_random_configs(n_runs, wave_id="local-sweep", scenario_level=scenario_level)

    print(f"Running {n_runs} simulations (parallel={n_parallel})...")
    start = time.monotonic()

    if n_parallel > 1:
        with mp.Pool(n_parallel) as pool:
            results = pool.map(run_simulation, configs)
    else:
        results = [run_simulation(c) for c in configs]

    elapsed = time.monotonic() - start

    # Sort by score descending
    results.sort(key=lambda r: r.final_score, reverse=True)

    print(f"\n=== Local Sweep Results ({n_runs} runs in {elapsed:.1f}s) ===")
    header = f"{'Rank':<6} {'Score':<8} {'Outcome':<12} {'Sol':<6}"
    print(header + f" {'Planted':<9} {'Harvested':<10} {'Crises'}")
    print("-" * 70)
    for rank, r in enumerate(results, 1):
        print(
            f"{rank:<6} {r.final_score:<8} {r.mission_outcome:<12} "
            f"{r.final_sol:<6} {r.crops_planted:<9} {r.crops_harvested:<10} "
            f"{r.crises_encountered}/{r.crises_resolved}"
        )
    print(f"\nBest score: {results[0].final_score}/100 (seed={results[0].seed})")


def _dispatch(args: argparse.Namespace) -> None:
    """Invoke the dispatcher Lambda to fan out a wave of simulations."""
    import boto3  # noqa: PLC0415

    wave_id = args.wave_id
    n_runs = getattr(args, "n_runs", 1000)
    mode = getattr(args, "mode", "random")
    base_wave_id = getattr(args, "base_wave_id", None)
    function_name = getattr(args, "function_name", "fast-sim-dispatcher")

    payload: dict[str, Any] = {
        "wave_id": wave_id,
        "n_runs": n_runs,
        "mode": mode,
    }
    if base_wave_id:
        payload["base_wave_id"] = base_wave_id

    print(f"Dispatching wave {wave_id} ({n_runs} runs, mode={mode})...")
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode(),
    )
    result = json.loads(response["Payload"].read())
    print(f"Dispatch result: {result}")


def _query(args: argparse.Namespace) -> None:
    """Query wave status and top-N results from DynamoDB/S3."""
    import boto3  # noqa: PLC0415

    wave_id = args.wave_id
    _top_n = getattr(args, "top_n", 10)  # reserved for future use
    table_name = getattr(args, "table", "fast-sim-waves")

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)  # type: ignore[attr-defined]

    # Get wave metadata (#META item)
    response = table.get_item(Key={"wave_id": wave_id, "run_id": "#META"})
    meta = response.get("Item")
    if not meta:
        print(f"No metadata found for wave {wave_id}")
        return

    total = int(meta.get("total_runs", 0))
    completed = int(meta.get("completed_runs", 0))
    status = meta.get("status", "unknown")
    best_score = meta.get("best_score", "N/A")

    pct = (completed / total * 100) if total > 0 else 0
    print(f"\n=== Wave {wave_id} ===")
    print(f"  Status:     {status}")
    print(f"  Progress:   {completed}/{total} ({pct:.1f}%)")
    print(f"  Best score: {best_score}")


def _aggregate(args: argparse.Namespace) -> None:
    """Manually trigger aggregation for a wave."""
    import boto3  # noqa: PLC0415

    wave_id = args.wave_id
    function_name = getattr(args, "function_name", "fast-sim-aggregator")

    print(f"Triggering aggregation for wave {wave_id}...")
    client = boto3.client("lambda")
    response = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"wave_id": wave_id}).encode(),
    )
    result = json.loads(response["Payload"].read())
    print(f"Aggregation result: {result}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="fast-sim",
        description="Mars Greenhouse Fast Simulation CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run-local
    p_local = subparsers.add_parser("run-local", help="Run single simulation locally")
    p_local.add_argument("--seed", type=int, default=42, help="Random seed")
    p_local.add_argument("--difficulty", default="normal", choices=["easy", "normal", "hard"])
    p_local.add_argument(
        "--scenario", type=int, default=3, choices=[0, 1, 2, 3],
        help="Scenario level: 0=no crises, 1=single crisis, 2=multi crisis, 3=full autonomous (default)",
    )
    p_local.set_defaults(func=_run_local)

    # local-sweep
    p_sweep = subparsers.add_parser("local-sweep", help="Run N simulations locally")
    p_sweep.add_argument("--n-runs", type=int, default=10, dest="n_runs")
    p_sweep.add_argument("--parallel", type=int, default=1)
    p_sweep.add_argument(
        "--scenario", type=int, default=3, choices=[0, 1, 2, 3],
        help="Scenario level: 0=no crises, 1=single crisis, 2=multi crisis, 3=full autonomous (default)",
    )
    p_sweep.set_defaults(func=_local_sweep)

    # dispatch
    p_dispatch = subparsers.add_parser("dispatch", help="Dispatch a wave to Lambda/SQS")
    p_dispatch.add_argument("--wave-id", required=True, dest="wave_id")
    p_dispatch.add_argument("--n-runs", type=int, default=1000, dest="n_runs")
    p_dispatch.add_argument("--mode", default="random", choices=["random", "evolve"])
    p_dispatch.add_argument("--base-wave-id", dest="base_wave_id")
    p_dispatch.add_argument("--function-name", default="fast-sim-dispatcher", dest="function_name")
    p_dispatch.set_defaults(func=_dispatch)

    # query
    p_query = subparsers.add_parser("query", help="Query wave status and results")
    p_query.add_argument("--wave-id", required=True, dest="wave_id")
    p_query.add_argument("--top-n", type=int, default=10, dest="top_n")
    p_query.add_argument("--table", default="fast-sim-waves")
    p_query.set_defaults(func=_query)

    # aggregate
    p_agg = subparsers.add_parser("aggregate", help="Manually trigger aggregation")
    p_agg.add_argument("--wave-id", required=True, dest="wave_id")
    p_agg.add_argument("--function-name", default="fast-sim-aggregator", dest="function_name")
    p_agg.set_defaults(func=_aggregate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
