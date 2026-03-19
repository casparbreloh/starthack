"""
Public surface of the simulation package.
Import sub-modules directly for internal use; this file exists for
IDE auto-complete and package-level introspection only.
"""

from src.catalog import CROP_CATALOG
from src.constants import CREW_SIZE, MISSION_DURATION_SOLS
from src.enums import CropType, CrewStatus
from src.state import engine

__all__ = [
    "CropType",
    "CrewStatus",
    "MISSION_DURATION_SOLS",
    "CREW_SIZE",
    "CROP_CATALOG",
    "engine",
]
