# ─────────────────────────────────────────────────────────────
# Hosted Agent container image
#
# For local Docker builds, use --platform linux/amd64:
#   docker build --platform linux/amd64 -t my-hosted-agent:latest .
#
# For ACR Tasks (cloud build), just run:
#   az acr build --registry <acr> --image <name>:<tag> .
#
# Foundry hosted agents run on Linux AMD64 infrastructure.
# ─────────────────────────────────────────────────────────────

FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (Docker layer caching)
COPY requirements_hosted.txt .
RUN pip install --no-cache-dir -r requirements_hosted.txt

# Copy the agent application
COPY agent_app.py .

# The hosting adapter listens on port 8088 by default
EXPOSE 8088

CMD ["python", "agent_app.py"]
