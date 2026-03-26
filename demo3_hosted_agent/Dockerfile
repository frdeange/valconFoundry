# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────
# Hosted Agent container image
#
# IMPORTANT: Always build with --platform linux/amd64
#   docker build --platform linux/amd64 -t my-hosted-agent:latest .
#
# Foundry hosted agents run on Linux AMD64 infrastructure.
# Images built for ARM64 (e.g. Apple Silicon) will fail at runtime.
# ─────────────────────────────────────────────────────────────

FROM --platform=linux/amd64 python:3.13-slim

WORKDIR /app

# Install dependencies first (Docker layer caching)
COPY requirements_hosted.txt .
RUN pip install --no-cache-dir -r requirements_hosted.txt

# Copy the agent application
COPY agent_app.py .

# The hosting adapter listens on port 8088 by default
EXPOSE 8088

CMD ["python", "agent_app.py"]
