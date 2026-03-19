"""Unit tests for action tool accumulation."""

from __future__ import annotations

import json

from src.tools.actions import bind_action_accumulator, create_action_tools


def test_create_action_tools_uses_explicit_accumulator():
    """Explicit accumulators collect queued actions."""
    actions: list[dict] = []
    tools = create_action_tools(action_accumulator=actions)

    result = tools["clean_water_filters"]()

    assert json.loads(result)["status"] == "queued"
    assert actions == [
        {"endpoint": "water/maintenance", "body": {"action": "clean_filters"}}
    ]


def test_create_action_tools_inherits_bound_accumulator():
    """Nested tool factories inherit the bound accumulator for specialists."""
    actions: list[dict] = []

    with bind_action_accumulator(actions):
        tools = create_action_tools()
        tools["allocate_energy"](
            heating_pct=47.0,
            lighting_pct=30.0,
            water_recycling_pct=12.0,
            nutrient_pumps_pct=5.0,
            reserve_pct=6.0,
        )

    assert actions == [
        {
            "endpoint": "energy/allocate",
            "body": {
                "heating_pct": 47.0,
                "lighting_pct": 30.0,
                "water_recycling_pct": 12.0,
                "nutrient_pumps_pct": 5.0,
                "reserve_pct": 6.0,
            },
        }
    ]
