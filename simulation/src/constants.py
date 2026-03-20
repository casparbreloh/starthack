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
CREW_DAILY_KCAL = 12_000  # 3,000 kcal/person/day (NASA HRP nutrition report)
CREW_DAILY_PROTEIN_G = 400  # 100 g/person/day (1.5 g/kg for 70 kg astronaut)
# 3.0 L/person/day drinking water (IOM 2004 adequate intake for active adult males)
# Total for crew of 4 = 12.0 L/sol
CREW_DAILY_WATER_L = 12.0

# ── Initial food rations (per food type, kg — freeze-dried/dehydrated equivalent)
# Sized to provide ~291-sol buffer (3.49M kcal) so the agent has time to ramp up
# greenhouse production. The greenhouse can produce ~4,600 kcal/sol at steady
# state, so the agent must actively farm to cover the remaining ~1.9M kcal.
# Potato: caloric backbone (77 kcal/100g × 3600 kg = 2 772 000 kcal)
# Beans:  protein source  (100 kcal/100g ×  700 kg = 700 000 kcal, 90 g prot/100g)
# Lettuce: micronutrient supplement (15 kcal/100g × 50 kg)
# Radish:  fast-cycle emergency buffer (16 kcal/100g × 25 kg)
# Herbs:   crew morale / flavour (40 kcal/100g × 15 kg)
INITIAL_FOOD_KG: dict[str, float] = {
    "potato": 3600.0,
    "beans": 700.0,
    "lettuce": 50.0,
    "radish": 25.0,
    "herbs": 15.0,
}
# Caloric and protein density per kg (matches CROP_CATALOG values × 10)
FOOD_KCAL_PER_KG: dict[str, float] = {
    "potato": 770.0,
    "beans": 1000.0,
    "lettuce": 150.0,
    "radish": 160.0,
    "herbs": 400.0,
}
FOOD_PROTEIN_G_PER_KG: dict[str, float] = {
    "potato": 20.0,
    "beans": 90.0,
    "lettuce": 13.0,
    "radish": 7.0,
    "herbs": 30.0,
}

# ── Initial stores (NORMAL difficulty) ───────────────────────────────────────
# Derived from INITIAL_FOOD_KG × FOOD_KCAL_PER_KG / FOOD_PROTEIN_G_PER_KG
# potato 2 772 000 + beans 700 000 + lettuce 7 500 + radish 4 000 + herbs 6 000
INITIAL_STORED_KCAL = 3_489_500  # ~291-sol buffer at 12,000 kcal/day
# potato 72 000 + beans 63 000 + lettuce 650 + radish 175 + herbs 450
INITIAL_STORED_PROTEIN_G = 136_275  # ~341-sol buffer at 400 g/day
INITIAL_WATER_RESERVOIR_L = 600.0  # +100 L added as mission starting ration
INITIAL_BATTERY_WH = 12_000.0
INITIAL_NUTRIENT_STOCK_PCT = 100.0

# ── Energy (Wh) ───────────────────────────────────────────────────────────────
BATTERY_CAPACITY_WH = 20_000.0
SOLAR_PANEL_AREA_M2 = 80.0
SOLAR_PANEL_EFFICIENCY = 0.18  # 18 %
EFFECTIVE_SOLAR_HOURS_PER_SOL = 8.0

# Subsystem base consumptions (Wh/sol)
HEATING_BASE_WH = 1_800.0  # at 0 °C outside
HEATING_PER_DEGREE_WH = 15.0  # additional per °C below 0 °C outside
LIGHTING_WH_PER_ZONE_PER_16H = 600.0  # per zone at full 16-hour photoperiod
RECYCLING_WH = 400.0
NUTRIENT_PUMPS_WH = 150.0
SENSORS_CONTROL_WH = 100.0

# ── Greenhouse zones (NORMAL difficulty) ──────────────────────────────────────
ZONE_AREAS_M2: dict[str, float] = {"A": 12.0, "B": 18.0, "C": 20.0}
TOTAL_GREENHOUSE_AREA_M2 = sum(ZONE_AREAS_M2.values())  # 50 m²

# ── Water system ──────────────────────────────────────────────────────────────
WATER_RESERVOIR_CAPACITY_L = 600.0
WATER_RECYCLING_NOMINAL_PCT = 93.0  # ISS ECLSS historical average (NASA 2023)
# Plant transpiration recovery: ECLSS Condensing Heat Exchanger captures ~80 % of
# moisture transpired by plants (NASA JSC-64122, Barta et al. 2005).
PLANT_TRANSPIRATION_RECOVERY_PCT = 80.0
FILTER_DEGRADATION_RATE_PCT_PER_SOL = 0.05
FILTER_HEALTH_MAINTENANCE_RESTORE = 15.0  # % restored by clean_filters action
FILTER_HEALTH_MIN_EFFICIENCY_FACTOR = 0.5  # recycling can fall to 50 % of nominal

# ── Ice mining ────────────────────────────────────────────────────────────────
# Source: docs/mcp-data/01_MARS_ENVIRONMENT_EXTENDED.MD §1.8: subsurface ice deposits
ICE_MINING_ENERGY_COST_WH = 800.0
ICE_MINING_BASE_YIELD_L = 15.0
ICE_MINING_MIN_YIELD_L = 5.0  # Yield formula: MIN + (BASE - MIN) * drill_health_pct / 100; range at usable health (10-100%): 6.0-15.0 L
ICE_MINING_DRILL_DEGRADATION_PCT = 5.0
ICE_MINING_DRILL_MAINTENANCE_RESTORE_PCT = 20.0
ICE_MINING_DRILL_MIN_HEALTH_PCT = 10.0
ICE_MINING_DRILL_INITIAL_HEALTH_PCT = 100.0

# ── Crew hydration model ──────────────────────────────────────────────────────
# Source: IOM 2004, WHO StatPearls NBK555956, medical consensus
DEHYDRATION_RATE_PCT_PER_SOL = 35.0  # hydration loss/sol at zero water (death ~3 sols)
HYDRATION_RECOVERY_RATE_PCT_PER_SOL = 25.0  # recovery speed when fully watered
HYDRATION_MILD_PCT = 95.0  # >5% deficit: thirst, dry mouth
HYDRATION_MODERATE_PCT = 80.0  # >20% deficit: headache, weakness, nausea
HYDRATION_SEVERE_PCT = 60.0  # >40% deficit: confusion, tachycardia, muscle cramps
HYDRATION_CRITICAL_PCT = 40.0  # >60% deficit: organ failure risk, life-threatening

# ── Crew radiation model ──────────────────────────────────────────────────────
# Source: Hassler et al. 2014, Science 343:1244797 (Curiosity RAD instrument)
MARS_SURFACE_RADIATION_MSV_PER_SOL = 0.67  # mSv/sol on unshielded Mars surface
HABITAT_RADIATION_SHIELDING_FACTOR = 0.45  # ~45% dose reduction inside habitat
# Inside dose: 0.67 × 0.55 ≈ 0.37 mSv/sol → ~166 mSv over 450-sol mission
CREW_RADIATION_DOSE_PER_SOL = MARS_SURFACE_RADIATION_MSV_PER_SOL * (
    1.0 - HABITAT_RADIATION_SHIELDING_FACTOR
)
RADIATION_WARNING_MSV = 100.0  # NASA occupational concern (NASA-STD-3001 Vol.1 Rev.B)
RADIATION_CRITICAL_MSV = 500.0  # Approaching 600 mSv career limit (NASA 2021 policy)
RADIATION_FATAL_MSV = 1000.0  # Acute Radiation Syndrome onset (WHO fact sheet)

# ── CO2 health effects ────────────────────────────────────────────────────────
# Source: OSHA 1910.1000, NASA-STD-3001 Vol.1, NIOSH NPG
CO2_IMPAIRMENT_PPM = 5000.0  # OSHA 8-h TWA PEL; early cognitive impairment
CO2_CRITICAL_PPM = 10000.0  # Dizziness, significant cognitive impairment (NIOSH)
CO2_DANGER_PPM = 30000.0  # NIOSH STEL; risk of loss of consciousness

# ── Crew temperature health ───────────────────────────────────────────────────
# Source: NASA-STD-3001 Vol.2 Rev.A §6.2.1; WHO housing & health guidelines
CREW_TEMP_COMFORT_MIN_C = 18.3  # NASA lower habitat comfort bound (65 °F)
CREW_TEMP_COMFORT_MAX_C = 26.7  # NASA upper habitat comfort bound (80 °F)
CREW_TEMP_HYPOTHERMIA_RISK_C = 10.0  # Hypothermia risk without insulation (WHO)
CREW_TEMP_HEATSTROKE_RISK_C = 35.0  # Heat stroke ambient onset (WHO/CDC)
CREW_TEMP_CRITICAL_LOW_C = 0.0  # Rapid hypothermia onset
CREW_TEMP_CRITICAL_HIGH_C = 45.0  # Rapid hyperthermia onset

# ── Starvation model ──────────────────────────────────────────────────────────
# Source: WHO TRS 724 (1985), Minnesota Starvation Study (Keys 1950)
# Thresholds for consecutive-deficit-sol counter → level transitions
STARVATION_ONSET_DEFICIT_SOLS = 3  # FED → UNDERFED   (sols 0–2 = FED)
STARVATION_SEVERE_DEFICIT_SOLS = 7  # UNDERFED → MALNOURISHED (sols 3–6)
STARVATION_CRITICAL_DEFICIT_SOLS = (
    11  # MALNOURISHED → STARVING (sols 7–10); death ~18 sols
)

# Caloric thresholds governing counter movement (asymmetric recovery)
STARVATION_FULL_RECOVERY_THRESHOLD_PCT = 1.0  # ≥100 % kcal → counter −3
STARVATION_DEFICIT_THRESHOLD_PCT = (
    0.8  # < 80 % kcal → counter +1; 80–100 % → counter −1
)

# Health penalty applied per sol at each starvation level (accumulates cumulatively)
STARVATION_PENALTY_UNDERFED_PER_SOL = 2.0  # max 8 pts over 4 UNDERFED sols
STARVATION_PENALTY_MALNOURISHED_PER_SOL = 5.0  # max 20 pts over 4 MALNOURISHED sols
STARVATION_PENALTY_STARVING_PER_SOL = 10.0  # 10 pts/sol → death ~8 STARVING sols

# ── Micronutrient model ───────────────────────────────────────────────────────
# Source: NASA-STD-3001 Vol.2 Rev.B §6.2.4; IOM Dietary Reference Intakes 2006
# Micronutrients (vitamins A, C, K, folate, minerals) come only from fresh crops
# (e.g. lettuce). Stored food lacks these after processing. Without a fresh
# source, subclinical deficiency begins within ~7 days; clinical symptoms emerge
# around 3 weeks (scurvy onset, immune dysfunction, bone loss).
MICRONUTRIENT_ONSET_DEFICIT_SOLS = 7  # ADEQUATE → DEFICIENT (subclinical)
MICRONUTRIENT_SEVERE_DEFICIT_SOLS = 21  # DEFICIENT → DEPLETED (clinical symptoms)
MICRONUTRIENT_PENALTY_DEFICIENT_PER_SOL = 1.0  # max 14 pts over 14 DEFICIENT sols
MICRONUTRIENT_PENALTY_DEPLETED_PER_SOL = 3.0  # 3 pts/sol → death ~50 DEPLETED sols

# ── Nutrient system ───────────────────────────────────────────────────────────
NUTRIENT_STOCK_DEGRADATION_PCT_PER_SOL = 0.08  # stock depletion rate
NUTRIENT_RESTOCK_AMOUNT_PCT = 10.0  # per /nutrients/adjust call

# ── Mars dust / atmosphere ────────────────────────────────────────────────────
# Beer-Lambert effective extinction coefficient for broadband solar through
# Martian dust (Tomasko et al. 1999, JGR 104:E8; Lemmon et al. 2015, Icarus 251)
MARS_DUST_EXTINCTION_COEFF = 0.9
# Regional dust storm optical depth in tau (Zurek & Martin 1993, JGR 98:E2;
# Smith 2004, Icarus 167:148–165; typical heavy regional storm ≈ 4 tau)
DUST_STORM_OPACITY_TAU = 4.0

# ── Mars orbital / climate ────────────────────────────────────────────────────
MARS_SOLS_PER_YEAR = 668
MARS_SOLAR_CONSTANT_WM2 = 1_361.0
MARS_SEMIMAJOR_AXIS_AU = 1.524
MARS_ECCENTRICITY = 0.093

# ── Environment targets & stress thresholds ───────────────────────────────────
TARGET_TEMP_C = 21.0
TARGET_CO2_PPM = 1_000.0
TARGET_HUMIDITY_PCT = 60.0
TARGET_PAR = 220.0  # µmol/m²/s
TARGET_PHOTOPERIOD_H = 16.0

STRESS_TEMP_HIGH_C = 25.0
STRESS_TEMP_LOW_C = 15.0
STRESS_CO2_LOW_PPM = 500.0
STRESS_HUMIDITY_HIGH_PCT = 85.0
STRESS_HUMIDITY_LOW_PCT = 30.0

# ── Light (PAR) stress ────────────────────────────────────────────────────────
# Source: Taiz & Zeiger "Plant Physiology" 5th ed.; Bugbee & Salisbury 1988
STRESS_PAR_CRITICAL_LOW = 50.0  # µmol/m²/s — growth stalls + severe health loss
STRESS_PAR_LOW = 100.0  # µmol/m²/s — sub-optimal light, mild health loss
STRESS_PAR_HIGH = 500.0  # µmol/m²/s — photoinhibition onset

# ── Potassium deficiency ──────────────────────────────────────────────────────
STRESS_K_DEFICIENCY_PPM = 30.0  # K below this → crop stress (weak stems, poor yield)

# ── Salinity / EC thresholds ─────────────────────────────────────────────────
# Source: Ayers & Westcot FAO Irrigation & Drainage Paper 29 Rev.1
STRESS_EC_MODERATE = 2.5  # mS/cm — moderate salinity stress begins
STRESS_EC_SEVERE = 3.5  # mS/cm — severe salinity stress (20–50% biomass loss)

# ── pH crop stress ────────────────────────────────────────────────────────────
# Optimal hydroponic pH 5.5–6.5; outside this → nutrient lockout
STRESS_PH_OPTIMAL_LOW = 5.5
STRESS_PH_OPTIMAL_HIGH = 6.5
STRESS_PH_CRITICAL_LOW = 5.0  # below → Fe/Mn toxicity risk
STRESS_PH_CRITICAL_HIGH = 7.0  # above → Fe/P precipitation, severe lockout

# ── Nutrient solution chemistry dynamics ─────────────────────────────────────
# Plant nutrient uptake acidifies solution (cation > anion uptake)
SALT_ACCUMULATION_PPM_PER_SOL = 1.5  # ppm/sol — passive mineral residue from water
PH_ACIDIFICATION_PER_SOL = 0.02  # pH units/sol drop when crops actively growing

# Nutrient solution targets
TARGET_PH = 5.8
TARGET_EC = 1.6  # mS/cm
TARGET_N_PPM = 150.0
TARGET_P_PPM = 40.0
TARGET_K_PPM = 180.0
TARGET_CA_PPM = 120.0
TARGET_DO_PPM = 7.0  # dissolved O₂

# ── Crew illness model ────────────────────────────────────────────────────────
# Illness occurs ~2 times per 450-sol mission (random per-sol check, no second
# illness while one is already active).
ILLNESS_PROBABILITY_PER_SOL: float = 2 / 450  # ≈0.44 % chance each sol
ILLNESS_MIN_DURATION_SOLS: int = 3
ILLNESS_MAX_DURATION_SOLS: int = 5
ILLNESS_KCAL_MULTIPLIER: float = 1.15  # +15 % caloric need while ill
ILLNESS_PROTEIN_MULTIPLIER: float = 1.20  # +20 % protein need while ill

# ── Scoring ───────────────────────────────────────────────────────────────────
WARNING_KCAL_DAYS = 5  # warn when < N days of food left
WARNING_WATER_DAYS = 3
CRISIS_WATER_RESERVOIR_L = 50.0
CRISIS_BATTERY_WH = 2_000.0
CRISIS_BATTERY_PCT = 5.0  # Battery below 5 % triggers interrupt
