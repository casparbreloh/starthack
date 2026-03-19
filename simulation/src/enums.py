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


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SensorStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    OFFLINE = "offline"


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
