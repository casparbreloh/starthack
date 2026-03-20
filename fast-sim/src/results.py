"""
RunResult schema — output from a single 450-sol simulation run.

Includes all per-run metrics, serialization to JSON, and flat Parquet rows.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunResult:
    """
    Complete output record for one simulation run.

    Fields are designed for both human readability and columnar storage (Parquet/Athena).
    """

    run_id: str
    wave_id: str
    config_hash: str  # SHA256 of JSON-serialized RunConfig for deduplication
    seed: int
    difficulty: str

    # Mission outcome
    final_sol: int  # last sol reached (450 if complete, less if failed)
    mission_outcome: str  # "complete" | "failed"
    final_score: int  # overall score 0-100

    # Sub-scores (from ScoreSnapshot)
    survival_score: int  # snapshot.survival["score"]
    nutrition_score: int  # snapshot.nutrition["score"]
    resource_efficiency_score: int  # snapshot.resource_efficiency["score"]
    crisis_mgmt_score: int  # snapshot.crisis_management["score"]

    # Crisis tracking
    crises_encountered: int
    crises_resolved: int
    crisis_log: list[dict[str, Any]] = field(default_factory=list)

    # Crop tracking
    crop_yields: dict[str, float] = field(default_factory=dict)
    crop_deaths: int = 0
    crops_planted: int = 0
    crops_harvested: int = 0

    # Resource extremes
    resource_extremes: dict[str, float] = field(
        default_factory=lambda: {
            "water_min_L": 0.0,
            "water_max_L": 0.0,
            "battery_min_pct": 0.0,
            "battery_max_pct": 0.0,
            "food_min_days": 0.0,
            "nutrient_min_pct": 0.0,
            "total_mined_liters": 0.0,
            "drill_health_min_pct": 100.0,
        }
    )

    # Resource averages
    resource_averages: dict[str, float] = field(
        default_factory=lambda: {
            "avg_water_L": 0.0,
            "avg_battery_pct": 0.0,
            "avg_food_days": 0.0,
        }
    )

    # Significant decisions
    key_decisions: list[dict[str, Any]] = field(default_factory=list)

    # Full config used (for reproducibility)
    strategy_config: dict[str, Any] = field(default_factory=dict)

    # Performance
    duration_seconds: float = 0.0

    # ---------------------------------------------------------------------------
    # Serialization
    # ---------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-compatible dictionary."""
        return {
            "run_id": self.run_id,
            "wave_id": self.wave_id,
            "config_hash": self.config_hash,
            "seed": self.seed,
            "difficulty": self.difficulty,
            "final_sol": self.final_sol,
            "mission_outcome": self.mission_outcome,
            "final_score": self.final_score,
            "survival_score": self.survival_score,
            "nutrition_score": self.nutrition_score,
            "resource_efficiency_score": self.resource_efficiency_score,
            "crisis_mgmt_score": self.crisis_mgmt_score,
            "crises_encountered": self.crises_encountered,
            "crises_resolved": self.crises_resolved,
            "crisis_log": self.crisis_log,
            "crop_yields": self.crop_yields,
            "crop_deaths": self.crop_deaths,
            "crops_planted": self.crops_planted,
            "crops_harvested": self.crops_harvested,
            "resource_extremes": self.resource_extremes,
            "resource_averages": self.resource_averages,
            "key_decisions": self.key_decisions,
            "strategy_config": self.strategy_config,
            "duration_seconds": self.duration_seconds,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunResult:
        """Deserialize from a dictionary."""
        return cls(
            run_id=str(data["run_id"]),
            wave_id=str(data["wave_id"]),
            config_hash=str(data["config_hash"]),
            seed=int(data["seed"]),
            difficulty=str(data["difficulty"]),
            final_sol=int(data["final_sol"]),
            mission_outcome=str(data["mission_outcome"]),
            final_score=int(data["final_score"]),
            survival_score=int(data["survival_score"]),
            nutrition_score=int(data["nutrition_score"]),
            resource_efficiency_score=int(data["resource_efficiency_score"]),
            crisis_mgmt_score=int(data["crisis_mgmt_score"]),
            crises_encountered=int(data["crises_encountered"]),
            crises_resolved=int(data["crises_resolved"]),
            crisis_log=list(data.get("crisis_log", [])),
            crop_yields={k: float(v) for k, v in data.get("crop_yields", {}).items()},
            crop_deaths=int(data.get("crop_deaths", 0)),
            crops_planted=int(data.get("crops_planted", 0)),
            crops_harvested=int(data.get("crops_harvested", 0)),
            resource_extremes=dict(data.get("resource_extremes", {})),
            resource_averages=dict(data.get("resource_averages", {})),
            key_decisions=list(data.get("key_decisions", [])),
            strategy_config=dict(data.get("strategy_config", {})),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
        )

    @classmethod
    def from_json(cls, json_str: str) -> RunResult:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def to_parquet_row(self) -> dict[str, Any]:
        """
        Return a flat dict suitable for a Parquet row.

        All nested structures are serialized to JSON strings.
        All scalar values remain as Python scalars.
        """
        return {
            "run_id": self.run_id,
            "wave_id": self.wave_id,
            "config_hash": self.config_hash,
            "seed": self.seed,
            "difficulty": self.difficulty,
            "final_sol": self.final_sol,
            "mission_outcome": self.mission_outcome,
            "final_score": self.final_score,
            "survival_score": self.survival_score,
            "nutrition_score": self.nutrition_score,
            "resource_efficiency_score": self.resource_efficiency_score,
            "crisis_mgmt_score": self.crisis_mgmt_score,
            "crises_encountered": self.crises_encountered,
            "crises_resolved": self.crises_resolved,
            "crisis_log_json": json.dumps(self.crisis_log),
            "crop_yields_json": json.dumps(self.crop_yields),
            "crop_deaths": self.crop_deaths,
            "crops_planted": self.crops_planted,
            "crops_harvested": self.crops_harvested,
            "resource_extremes_json": json.dumps(self.resource_extremes),
            "resource_averages_json": json.dumps(self.resource_averages),
            "key_decisions_json": json.dumps(self.key_decisions),
            "strategy_config_json": json.dumps(self.strategy_config),
            "duration_seconds": self.duration_seconds,
        }


def compute_config_hash(config_dict: dict[str, Any]) -> str:
    """Compute a stable SHA256 hash of a config dictionary for deduplication."""
    canonical = json.dumps(config_dict, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
