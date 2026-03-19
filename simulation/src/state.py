"""
Singleton session manager instance.

Import `session_manager` from this module wherever you need access to
simulation sessions. There is exactly one SessionManager per process,
with a default session created on init so bare REST calls keep working.
"""

from src.session import SessionManager

session_manager = SessionManager()
