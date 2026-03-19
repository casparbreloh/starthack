from enum import StrEnum


class CropType(StrEnum):
    LETTUCE = "lettuce"
    POTATO = "potato"
    RADISH = "radish"
    BEANS = "beans"
    HERBS = "herbs"


class MissionPhase(StrEnum):
    ACTIVE = "active"
    COMPLETE = "complete"
    FAILED = "failed"


class CrewStatus(StrEnum):
    NOMINAL = "nominal"
    WARNING = "warning"
    CRITICAL = "critical"
    DEAD = "dead"


class DehydrationLevel(StrEnum):
    """
    Dehydration severity levels based on hydration_pct.
    Source: WHO StatPearls NBK555956; IOM Dietary Reference Intakes 2004.
    """

    HYDRATED = "hydrated"  # >= 95 %: no deficit
    MILD = "mild"  # 80–95 %: thirst, dry mouth, reduced performance
    MODERATE = "moderate"  # 60–80 %: headache, weakness, nausea
    SEVERE = "severe"  # 40–60 %: confusion, tachycardia, muscle cramps
    CRITICAL = "critical"  # < 40 %: organ failure risk, life-threatening


class StarvationLevel(StrEnum):
    """
    Starvation severity based on consecutive caloric-deficit sols.
    Source: WHO TRS 724 (1985); Minnesota Starvation Study (Keys 1950).
    """

    FED = "fed"  # < 3 deficit sols: no health impact
    UNDERFED = "underfed"  # 3–14 deficit sols: fatigue, immune decline
    MALNOURISHED = "malnourished"  # 14–45 deficit sols: muscle wasting, organ stress
    STARVING = "starving"  # > 45 deficit sols: critical, life-threatening


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Difficulty(StrEnum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


class CrisisType(StrEnum):
    WATER_RECYCLING_DECLINE = "water_recycling_decline"
    ENERGY_DISRUPTION = "energy_disruption"
    PATHOGEN_OUTBREAK = "pathogen_outbreak"
    TEMPERATURE_FAILURE = "temperature_failure"
    CO2_IMBALANCE = "co2_imbalance"
    NUTRIENT_DEPLETION = "nutrient_depletion"
    FOOD_SHORTAGE = "food_shortage"
    WATER_SHORTAGE = "water_shortage"
    # New health crises
    CREW_DEHYDRATION = "crew_dehydration"  # crew hydration below safe threshold
    CREW_STARVATION = "crew_starvation"  # consecutive caloric deficit accumulating
    RADIATION_EXPOSURE = "radiation_exposure"  # cumulative dose exceeds NASA limit
    DUST_STORM = "dust_storm"  # active dust storm reducing solar irradiance


class CrewCauseOfDeath(StrEnum):
    DEHYDRATION = "dehydration"
    STARVATION = "starvation"
    RADIATION = "radiation"
    HYPOTHERMIA = "hypothermia"
    HYPERTHERMIA = "hyperthermia"
    CO2_TOXICITY = "co2_toxicity"
