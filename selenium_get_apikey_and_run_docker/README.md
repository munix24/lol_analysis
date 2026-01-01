# Docker Orchestrator

This container runs `docker_get_apikey_and_run.py`, which reads `apikey.txt` and starts the `munix244/lol_analysis_app` container with the key.

Important: It does not bundle Selenium/Firefox. Provide `apikey.txt` via a volume and set `--force-get False` (default).

## Build

```powershell
# From the folder containing the Dockerfile
docker build -t lol-orchestrator .
```

## Run (Windows + Docker Desktop)

- Ensure `apikey.txt` exists in your project folder and contains your Riot API key.
- This container uses the host Docker daemon. Mount the Docker socket and your project folder.

```powershell
# Mount Docker socket and the local folder (for apikey.txt)
# The default CMD already sets --force-get False

docker run --rm -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "${PWD}:/app" \
  lol-orchestrator
```

### Override options

```powershell
# Example: custom image/name/restart policy

docker run --rm -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "${PWD}:/app" \
  lol-orchestrator \
  --image munix244/lol_analysis_app \
  --name lol_analysis_app \
  --restart-on-failure 3
```

## Notes

- If you prefer retrieving the key via Selenium inside the container, you'll need to extend the image to install `selenium`, `firefox`, and `geckodriver`, and expose VNC or X11 for interactive login.
- Running `docker` inside the container uses the host daemon via `/var/run/docker.sock`. This pattern is widely used for orchestrators.
