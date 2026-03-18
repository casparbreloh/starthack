"""
All numeric mission constants. No logic, no imports.
Values are calibrated to be physically directional and produce interesting
agent decisions without requiring exact physical accuracy.
"""

# ── Mission ────────────────────────────────────────────────────────────────
MISSION_DURATION_SOLS = 450
CREW_SIZE = 4

# ── Crew daily needs (4 astronauts total) ──────────────────────────────────
CREW_DAILY_KCAL = 12_000
CREW_DAILY_PROTEIN_G = 400
CREW_DAILY_WATER_L = 9.0          # drinking water only (not irrigation)

# ── Initial stores (NORMAL difficulty) ────────────────────────────────────
INITIAL_STORED_KCAL = 1_200_000   # ~100-sol buffer
INITIAL_STORED_PROTEIN_G = 45_000
INITIAL_WATER_RESERVOIR_L = 500.0
INITIAL_BATTERY_WH = 12_000.0
INITIAL_NUTRIENT_STOCK_PCT = 100.0

# ── Energy (Wh) ────────────────────────────────────────────────────────────
BATTERY_CAPACITY_WH = 20_000.0
SOLAR_PANEL_AREA_M2 = 80.0
SOLAR_PANEL_EFFICIENCY = 0.18      # 18 %
EFFECTIVE_SOLAR_HOURS_PER_SOL = 8.0

# Subsystem base consumptions (Wh/sol)
HEATING_BASE_WH = 1_800.0          # at 0 °C outside
HEATING_PER_DEGREE_WH = 15.0       # additional per °C below 0 °C outside
LIGHTING_WH_PER_ZONE_PER_16H = 600.0  # per zone at full 16-hour photoperiod
RECYCLING_WH = 400.0
NUTRIENT_PUMPS_WH = 150.0
SENSORS_CONTROL_WH = 100.0

# ── Greenhouse zones (NORMAL difficulty) ─────────────────────────────────
ZONE_AREAS_M2: dict[str, float] = {"A": 12.0, "B": 18.0, "C": 20.0}
TOTAL_GREENHOUSE_AREA_M2 = sum(ZONE_AREAS_M2.values())   # 50 m²

# ── Water system ──────────────────────────────────────────────────────────
WATER_RESERVOIR_CAPACITY_L = 600.0
WATER_RECYCLING_NOMINAL_PCT = 91.5       # percent
FILTER_DEGRADATION_RATE_PCT_PER_SOL = 0.05
FILTER_HEALTH_MAINTENANCE_RESTORE = 15.0  # % restored by clean_filters action
FILTER_HEALTH_MIN_EFFICIENCY_FACTOR = 0.5  # recycling can fall to 50 % of nominal

# ── Nutrient system ────────────────────────────────────────────────────────
NUTRIENT_STOCK_DEGRADATION_PCT_PER_SOL = 0.08   # stock depletion rate
NUTRIENT_RESTOCK_AMOUNT_PCT = 10.0               # per /nutrients/adjust call

# ── Mars orbital / climate ────────────────────────────────────────────────
MARS_SOLS_PER_YEAR = 668
MARS_SOLAR_CONSTANT_WM2 = 1_361.0
MARS_SEMIMAJOR_AXIS_AU = 1.524
MARS_ECCENTRICITY = 0.093

# ── Environment targets & stress thresholds ───────────────────────────────
TARGET_TEMP_C = 21.0
TARGET_CO2_PPM = 1_000.0
TARGET_HUMIDITY_PCT = 60.0
TARGET_PAR = 220.0                 # µmol/m²/s
TARGET_PHOTOPERIOD_H = 16.0

STRESS_TEMP_HIGH_C = 25.0
STRESS_TEMP_LOW_C = 15.0
STRESS_CO2_LOW_PPM = 500.0
STRESS_HUMIDITY_HIGH_PCT = 85.0
STRESS_HUMIDITY_LOW_PCT = 30.0

# Nutrient solution targets
TARGET_PH = 5.8
TARGET_EC = 1.6                    # mS/cm
TARGET_N_PPM = 150.0
TARGET_P_PPM = 40.0
TARGET_K_PPM = 180.0
TARGET_CA_PPM = 120.0
TARGET_DO_PPM = 7.0                # dissolved O₂

# ── Scoring ────────────────────────────────────────────────────────────────
WARNING_KCAL_DAYS = 5              # warn when < N days of food left
WARNING_WATER_DAYS = 3
CRISIS_WATER_RESERVOIR_L = 50.0
CRISIS_BATTERY_WH = 2_000.0
