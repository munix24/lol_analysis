# Orchestrator container for running the LOL analysis app via Docker
# Uses Python + Docker CLI and expects apikey.txt to be mounted.
# Note: This does NOT include Selenium/Firefox; pass --force-get False and provide apikey.txt.

FROM python:3.11-alpine

# Install docker CLI to talk to host daemon via /var/run/docker.sock
RUN apk add --no-cache docker-cli

WORKDIR /app

# Copy project files
COPY . /app

# No third-party Python deps required for orchestrator
# If you later need Selenium, add: RUN pip install selenium

# Default command runs orchestrator using mounted apikey.txt
# - Mount /var/run/docker.sock for Docker access
# - Mount host folder so apikey.txt is available
ENTRYPOINT ["python", "docker_get_apikey_and_run.py"]
CMD ["--force-get", "False", "--outputFileName", "apikey.txt"]
