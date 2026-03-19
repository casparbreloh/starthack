"""Simulation API client for the Mars greenhouse agent system.

Wraps all simulation GET and POST endpoints with typed methods,
returning structured data (dicts). All endpoint paths are explicit.
"""

from __future__ import annotations

import httpx


class SimClient:
    """HTTP client for the Mars greenhouse simulation API."""

    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=30.0)

    # ------------------------------------------------------------------
    # Telemetry (GET)
    # ------------------------------------------------------------------

    def get_sim_status(self) -> dict:
        """GET /sim/status"""
        r = self.client.get("/sim/status")
        r.raise_for_status()
        return r.json()

    def get_weather_current(self) -> dict:
        """GET /weather/current"""
        r = self.client.get("/weather/current")
        r.raise_for_status()
        return r.json()

    def get_weather_history(self, last_n_sols: int = 30) -> list:
        """GET /weather/history?last_n_sols=N"""
        r = self.client.get("/weather/history", params={"last_n_sols": last_n_sols})
        r.raise_for_status()
        return r.json()

    def get_weather_forecast(self, horizon: int = 7) -> list:
        """GET /weather/forecast?horizon=N"""
        r = self.client.get("/weather/forecast", params={"horizon": horizon})
        r.raise_for_status()
        return r.json()

    def get_energy_status(self) -> dict:
        """GET /energy/status"""
        r = self.client.get("/energy/status")
        r.raise_for_status()
        return r.json()

    def get_greenhouse_environment(self) -> dict:
        """GET /greenhouse/environment"""
        r = self.client.get("/greenhouse/environment")
        r.raise_for_status()
        return r.json()

    def get_water_status(self) -> dict:
        """GET /water/status"""
        r = self.client.get("/water/status")
        r.raise_for_status()
        return r.json()

    def get_crops_status(self) -> dict:
        """GET /crops/status"""
        r = self.client.get("/crops/status")
        r.raise_for_status()
        return r.json()

    def get_nutrients_status(self) -> dict:
        """GET /nutrients/status"""
        r = self.client.get("/nutrients/status")
        r.raise_for_status()
        return r.json()

    def get_crew_nutrition(self) -> dict:
        """GET /crew/nutrition"""
        r = self.client.get("/crew/nutrition")
        r.raise_for_status()
        return r.json()

    def get_sensors_readings(self) -> dict:
        """GET /sensors/readings"""
        r = self.client.get("/sensors/readings")
        r.raise_for_status()
        return r.json()

    def get_events_log(self, since_sol: int = 0) -> list:
        """GET /events/log?since_sol=N"""
        r = self.client.get("/events/log", params={"since_sol": since_sol})
        r.raise_for_status()
        return r.json()

    def get_active_crises(self) -> dict:
        """GET /events/active_crises"""
        r = self.client.get("/events/active_crises")
        r.raise_for_status()
        return r.json()

    def get_score_current(self) -> dict:
        """GET /score/current"""
        r = self.client.get("/score/current")
        r.raise_for_status()
        return r.json()

    def get_score_final(self) -> dict:
        """GET /score/final — only call when mission_phase == 'complete', raises HTTP 400 otherwise."""
        r = self.client.get("/score/final")
        r.raise_for_status()
        return r.json()

    def get_crop_catalog(self) -> dict:
        """GET /crops/catalog — static crop data; call once on sol 0, not every sol."""
        r = self.client.get("/crops/catalog")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Actions (POST)
    # ------------------------------------------------------------------

    def allocate_energy(
        self,
        heating_pct: float,
        lighting_pct: float,
        water_recycling_pct: float,
        nutrient_pumps_pct: float,
        reserve_pct: float,
    ) -> dict:
        """POST /energy/allocate"""
        r = self.client.post(
            "/energy/allocate",
            json={
                "heating_pct": heating_pct,
                "lighting_pct": lighting_pct,
                "water_recycling_pct": water_recycling_pct,
                "nutrient_pumps_pct": nutrient_pumps_pct,
                "reserve_pct": reserve_pct,
            },
        )
        r.raise_for_status()
        return r.json()

    def set_environment(
        self,
        zone_id: str,
        target_temp_c: float | None = None,
        target_humidity_pct: float | None = None,
        target_co2_ppm: float | None = None,
        par_umol_m2s: float | None = None,
        photoperiod_hours: float | None = None,
    ) -> dict:
        """POST /greenhouse/set_environment"""
        body: dict = {"zone_id": zone_id}
        if target_temp_c is not None:
            body["target_temp_c"] = target_temp_c
        if target_humidity_pct is not None:
            body["target_humidity_pct"] = target_humidity_pct
        if target_co2_ppm is not None:
            body["target_co2_ppm"] = target_co2_ppm
        if par_umol_m2s is not None:
            body["par_umol_m2s"] = par_umol_m2s
        if photoperiod_hours is not None:
            body["photoperiod_hours"] = photoperiod_hours
        r = self.client.post("/greenhouse/set_environment", json=body)
        r.raise_for_status()
        return r.json()

    def set_irrigation(
        self,
        zone_id: str,
        irrigation_liters_per_sol: float,
        irrigation_frequency: str = "continuous",
    ) -> dict:
        """POST /water/set_irrigation.

        Note: The JSON key is 'irrigation_liters_per_sol', NOT 'liters_per_sol'.
        The optional 'irrigation_frequency' defaults to 'continuous' which is
        appropriate for all scenarios.
        """
        r = self.client.post(
            "/water/set_irrigation",
            json={
                "zone_id": zone_id,
                "irrigation_liters_per_sol": irrigation_liters_per_sol,
                "irrigation_frequency": irrigation_frequency,
            },
        )
        r.raise_for_status()
        return r.json()

    def water_maintenance(self, action: str = "clean_filters") -> dict:
        """POST /water/maintenance"""
        r = self.client.post("/water/maintenance", json={"action": action})
        r.raise_for_status()
        return r.json()

    def plant_crop(
        self,
        crop_type: str,
        zone_id: str,
        area_m2: float,
        batch_name: str | None = None,
    ) -> dict:
        """POST /crops/plant.

        Note: The JSON key is 'type', NOT 'crop_type'.
        """
        body: dict = {"type": crop_type, "zone_id": zone_id, "area_m2": area_m2}
        if batch_name is not None:
            body["batch_name"] = batch_name
        r = self.client.post("/crops/plant", json=body)
        r.raise_for_status()
        return r.json()

    def harvest_crop(self, crop_id: str) -> dict:
        """POST /crops/harvest"""
        r = self.client.post("/crops/harvest", json={"crop_id": crop_id})
        r.raise_for_status()
        return r.json()

    def remove_crop(self, crop_id: str, reason: str = "") -> dict:
        """POST /crops/remove"""
        r = self.client.post(
            "/crops/remove", json={"crop_id": crop_id, "reason": reason}
        )
        r.raise_for_status()
        return r.json()

    def adjust_nutrients(
        self,
        zone_id: str,
        target_ph: float | None = None,
        target_ec_ms_cm: float | None = None,
        nitrogen_boost: bool = False,
        potassium_boost: bool = False,
    ) -> dict:
        """POST /nutrients/adjust.

        Note: The JSON key is 'target_ec_ms_cm', NOT 'target_ec'.
        """
        body: dict = {
            "zone_id": zone_id,
            "nitrogen_boost": nitrogen_boost,
            "potassium_boost": potassium_boost,
        }
        if target_ph is not None:
            body["target_ph"] = target_ph
        if target_ec_ms_cm is not None:
            body["target_ec_ms_cm"] = target_ec_ms_cm
        r = self.client.post("/nutrients/adjust", json=body)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Control (POST)
    # ------------------------------------------------------------------

    def advance(self, sols: int = 1) -> dict:
        """POST /sim/advance — advances simulation by N sols; returns response JSON with events."""
        r = self.client.post("/sim/advance", json={"sols": sols})
        r.raise_for_status()
        return r.json()

    def reset(self, seed: int = 0, difficulty: str = "normal") -> dict:
        """POST /sim/reset"""
        r = self.client.post(
            "/sim/reset", json={"seed": seed, "difficulty": difficulty}
        )
        r.raise_for_status()
        return r.json()

    def log_decision(
        self,
        sol: int,
        decisions: list[dict | str],
        weather_forecast_used: dict | str | None = None,
        risk_assessment: str = "nominal",
    ) -> dict:
        """POST /agent/log_decision

        decisions: list of dicts (simulation expects list[dict[str, Any]]).
        If strings are passed, they are wrapped as {"action": s}.
        """
        wrapped = [d if isinstance(d, dict) else {"action": d} for d in decisions]
        body: dict = {
            "sol": sol,
            "decisions": wrapped,
            "risk_assessment": risk_assessment,
        }
        if weather_forecast_used is not None:
            body["weather_forecast_used"] = (
                weather_forecast_used
                if isinstance(weather_forecast_used, dict)
                else {"summary": weather_forecast_used}
            )
        r = self.client.post("/agent/log_decision", json=body)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def read_all_telemetry(self) -> dict:
        """Read all 14 telemetry endpoints and return as a combined dict.

        Keys: sim_status, weather_current, weather_history, weather_forecast,
              energy_status, greenhouse_environment, water_status, crops_status,
              nutrients_status, crew_nutrition, sensors_readings, events_log,
              active_crises, score_current.

        NOT included: get_score_final (raises HTTP 400 unless mission complete),
                      get_crop_catalog (static — call once on init via get_crop_catalog()).

        Size bounding applied:
          - events_log: only last 50 sols of events (since_sol = current_sol - 50)
          - weather_history: only last 30 sols via last_n_sols=30
        """
        sim_status = self.get_sim_status()
        current_sol = sim_status.get("current_sol", 0)
        events_since = max(0, current_sol - 50)

        return {
            "sim_status": sim_status,
            "weather_current": self.get_weather_current(),
            "weather_history": self.get_weather_history(last_n_sols=30),
            "weather_forecast": self.get_weather_forecast(),
            "energy_status": self.get_energy_status(),
            "greenhouse_environment": self.get_greenhouse_environment(),
            "water_status": self.get_water_status(),
            "crops_status": self.get_crops_status(),
            "nutrients_status": self.get_nutrients_status(),
            "crew_nutrition": self.get_crew_nutrition(),
            "sensors_readings": self.get_sensors_readings(),
            "events_log": self.get_events_log(since_sol=events_since),
            "active_crises": self.get_active_crises(),
            "score_current": self.get_score_current(),
        }
