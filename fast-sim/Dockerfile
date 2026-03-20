# Lambda container image for fast-sim
# Base: AWS Lambda Python 3.13 runtime
FROM public.ecr.aws/lambda/python:3.13

# Install fast-sim Python dependencies
RUN pip install --no-cache-dir \
    boto3 \
    bedrock-agentcore \
    pyarrow

# Copy simulation engine source
# Must maintain package structure so "from src.xxx import" works
COPY simulation/src/ /var/task/simulation/src/

# Copy fast-sim source
COPY fast-sim/src/ /var/task/fast_sim/

# Set PYTHONPATH so both simulation and fast_sim imports resolve:
#   from src.engine import SimulationEngine  -> /var/task/simulation/src/engine.py
#   from fast_sim.handlers import ...         -> /var/task/fast_sim/handlers.py
ENV PYTHONPATH=/var/task/simulation:/var/task

# Default handler (overridden per Lambda function via CMD in CDK)
CMD ["fast_sim.handlers.worker_handler"]
