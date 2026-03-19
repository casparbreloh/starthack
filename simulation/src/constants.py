"""
All numeric mission constants. No logic, no imports.
Values are calibrated to be physically directional and produce interesting
agent decisions without requiring exact physical accuracy.

Sources cited inline:
  IOM 2004     — Dietary Reference Intakes for Water (Institute of Medicine)
  NASA HIDH    — Human Integration Design Handbook JSC-20237
  Hassler 2014 — Curiosity RAD data, Science 343:1244797
  NASA-STD-3001 — Human Integration Design Standards Vol.1 & Vol.2
  OSHA 1910.1000 — Air Contaminants standard
  WHO TRS 724  — Technical Report Series on Nutrition
"""

# ── Mission ────────────────────────────────────────────────────────────────────
MISSION_DURATION_SOLS = 450
CREW_SIZE = 4

# ── Crew daily needs (4 astronauts total) ─────────────────────────────────────
CREW_DAILY_KCAL = 12_000           # 3,000 kcal/person/day (NASA HRP nutrition report)
CREW_DAILY_PROTEIN_G = 400         # 100 g/person/day (1.5 g/kg for 70 kg astronaut)
# 3.0 L/person/day drinking water (IOM 2004 adequate intake for active adult males)
# Total for crew of 4 = 12.0 L/sol
CREW_DAILY_WATER_L = 12.0

# ── Initial stores (NORMAL difficulty) ───────────────────────────────────────
INITIAL_STORED_KCAL = 1_200_000   # ~100-sol buffer
INITIAL_STORED_PROTEIN_G = 45_000
INITIAL_WATER_RESERVOIR_L = 500.0
INITIAL_BATTERY_WH = 12_000.0
INITIAL_NUTRIENT_STOCK_PCT = 100.0

# ── Energy (Wh) ───────────────────────────────────────────────────────────────
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

# ── Greenhouse zones (NORMAL difficulty) ──────────────────────────────────────
ZONE_AREAS_M2: dict[str, float] = {"A": 12.0, "B": 18.0, "C": 20.0}
TOTAL_GREENHOUSE_AREA_M2 = sum(ZONE_AREAS_M2.values())   # 50 m²

# ── Water system ──────────────────────────────────────────────────────────────
WATER_RESERVOIR_CAPACITY_L = 600.0
WATER_RECYCLING_NOMINAL_PCT = 93.0       # ISS ECLSS historical average (NASA 2023)
FILTER_DEGRADATION_RATE_PCT_PER_SOL = 0.05
FILTER_HEALTH_MAINTENANCE_RESTORE = 15.0  # % restored by clean_filters action
FILTER_HEALTH_MIN_EFFICIENCY_FACTOR = 0.5  # recycling can fall to 50 % of nominal

# ── Crew hydration model ──────────────────────────────────────────────────────
# Source: IOM 2004, WHO StatPearls NBK555956, medical consensus
DEHYDRATION_RATE_PCT_PER_SOL = 35.0      # hydration loss/sol at zero water (death ~3 sols)
HYDRATION_RECOVERY_RATE_PCT_PER_SOL = 25.0  # recovery speed when fully watered
HYDRATION_MILD_PCT = 95.0          # >5% deficit: thirst, dry mouth
HYDRATION_MODERATE_PCT = 80.0      # >20% deficit: headache, weakness, nausea
HYDRATION_SEVERE_PCT = 60.0        # >40% deficit: confusion, tachycardia, muscle cramps
HYDRATION_CRITICAL_PCT = 40.0      # >60% deficit: organ failure risk, life-threatening

# ── Crew radiation model ──────────────────────────────────────────────────────
# Source: Hassler et al. 2014, Science 343:1244797 (Curiosity RAD instrument)
MARS_SURFACE_RADIATION_MSIV_PER_SOL = 0.67   # mSv/sol on unshielded Mars surface
HABITAT_RADIATION_SHIELDING_FACTOR = 0.45    # ~45% dose reduction inside habitat
# Inside dose: 0.67 × 0.55 ≈ 0.37 mSv/sol → ~166 mSv over 450-sol mission
CREW_RADIATION_DOSE_PER_SOL = MARS_SURFACE_RADIATION_MSIV_PER_SOL * (1.0 - HABITAT_RADIATION_SHIELDING_FACTOR)
RADIATION_WARNING_MSV = 100.0    # NASA occupational concern (NASA-STD-3001 Vol.1 Rev.B)
RADIATION_CRITICAL_MSV = 500.0   # Approaching 600 mSv career limit (NASA 2021 policy)
RADIATION_FATAL_MSV = 1000.0     # Acute Radiation Syndrome onset (WHO fact sheet)

# ── CO2 health effects ────────────────────────────────────────────────────────
# Source: OSHA 1910.1000, NASA-STD-3001 Vol.1, NIOSH NPG
CO2_IMPAIRMENT_PPM = 5000.0      # OSHA 8-h TWA PEL; early cognitive impairment
CO2_CRITICAL_PPM = 10000.0       # Dizziness, significant cognitive impairment (NIOSH)
CO2_DANGER_PPM = 30000.0         # NIOSH STEL; risk of loss of consciousness

# ── Crew temperature health ───────────────────────────────────────────────────
# Source: NASA-STD-3001 Vol.2 Rev.A §6.2.1; WHO housing & health guidelines
CREW_TEMP_COMFORT_MIN_C = 18.3   # NASA lower habitat comfort bound (65 °F)
CREW_TEMP_COMFORT_MAX_C = 26.7   # NASA upper habitat comfort bound (80 °F)
CREW_TEMP_HYPOTHERMIA_RISK_C = 10.0   # Hypothermia risk without insulation (WHO)
CREW_TEMP_HEATSTROKE_RISK_C = 35.0    # Heat stroke ambient onset (WHO/CDC)
CREW_TEMP_CRITICAL_LOW_C = 0.0        # Rapid hypothermia onset
CREW_TEMP_CRITICAL_HIGH_C = 45.0      # Rapid hyperthermia onset

# ── Starvation model ──────────────────────────────────────────────────────────
# Source: WHO TRS 724 (1985), Minnesota Starvation Study (Keys 1950)
STARVATION_ONSET_DEFICIT_SOLS = 3      # Health effects start after 3 consecutive severe-deficit sols
STARVATION_SEVERE_DEFICIT_SOLS = 14    # Significant muscle catabolism at 14+ sols
STARVATION_CRITICAL_DEFICIT_SOLS = 45  # Death range: 30–70 sols without food (WHO TRS 724)
STARVATION_CALORIC_THRESHOLD_PCT = 0.6 # <60% of daily kcal target = severe-deficit sol

# ── Nutrient system ───────────────────────────────────────────────────────────
NUTRIENT_STOCK_DEGRADATION_PCT_PER_SOL = 0.08   # stock depletion rate
NUTRIENT_RESTOCK_AMOUNT_PCT = 10.0               # per /nutrients/adjust call

# ── Mars orbital / climate ────────────────────────────────────────────────────
MARS_SOLS_PER_YEAR = 668
MARS_SOLAR_CONSTANT_WM2 = 1_361.0
MARS_SEMIMAJOR_AXIS_AU = 1.524
MARS_ECCENTRICITY = 0.093

# ── Environment targets & stress thresholds ───────────────────────────────────
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

# ── Scoring ───────────────────────────────────────────────────────────────────
WARNING_KCAL_DAYS = 5              # warn when < N days of food left
WARNING_WATER_DAYS = 3
CRISIS_WATER_RESERVOIR_L = 50.0
CRISIS_BATTERY_WH = 2_000.0
