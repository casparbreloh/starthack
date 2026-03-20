"""AWS Lambda handler — wraps the FastAPI app via Mangum."""

from mangum import Mangum

from serve import app

handler = Mangum(app, lifespan="on")
