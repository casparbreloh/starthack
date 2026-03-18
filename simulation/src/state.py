"""
Singleton simulation engine instance.

Import `engine` from this module wherever you need access to the running
simulation state. There is exactly one instance per process.
"""

from src.engine import SimulationEngine

engine = SimulationEngine()
