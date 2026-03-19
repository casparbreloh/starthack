from enum import Enum


class CropType(str, Enum):
    LETTUCE = "lettuce"
    POTATO = "potato"
    RADISH = "radish"
    BEANS = "beans"
    HERBS = "herbs"


class MissionPhase(str, Enum):
    ACTIVE = "active"
    COMPLETE = "complete"
    FAILED = "failed"


class CrewStatus(str, Enum):
    NOMINAL = "nominal"
    WARNING = "warning"
    CRITICAL = "critical"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SensorStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    OFFLINE = "offline"


class Difficulty(str, Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


class CrisisType(str, Enum):
    WATER_RECYCLING_DECLINE = "water_recycling_decline"
    ENERGY_DISRUPTION = "energy_disruption"
    PATHOGEN_OUTBREAK = "pathogen_outbreak"
    TEMPERATURE_FAILURE = "temperature_failure"
    CO2_IMBALANCE = "co2_imbalance"
    NUTRIENT_DEPLETION = "nutrient_depletion"
    FOOD_SHORTAGE = "food_shortage"
    WATER_SHORTAGE = "water_shortage"
