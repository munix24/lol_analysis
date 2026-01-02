#!/usr/bin/env python3
"""Run the `munix244/lol_analysis_app` container with a Riot API key.

This replicates the behavior of the project's batch file but implemented in Python:
- prompt for API key (or accept via `--apikey`)
- fallback to `apikey.txt` in script folder or the `riotapikey` env var
- mask the displayed key
- ensure Docker is available
- remove any existing container with the same name
- run `docker run -d --restart=on-failure:N --name <name> -e riotapikey=<key> <image>`

Usage:
  python docker_run_w_apikey_lol_analysis_app.py
  python docker_run_w_apikey_lol_analysis_app.py --apikey MYKEY
  python docker_run_w_apikey_lol_analysis_app.py --restart-on-failure 5
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_IMAGE = "munix244/lol_analysis_app"
DEFAULT_NAME = "lol_analysis_app"
DEFAULT_RESTART_ON_FAILURE = 3

def read_apikey_from_file(scriptdir: Path) -> str | None:
    if not scriptdir.exists():
        return None
    try:
        for line in scriptdir.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s:
                return s
    except Exception:
        return None
    return None

def mask_key(key: str) -> str:
    if not key:
        return "****"
    if len(key) <= 4:
        return "****" + key
    return "****" + key[-4:]

def check_docker_available() -> bool:
    docker_path = shutil.which("docker")
    if docker_path is None:
        return False
    try:
        completed = subprocess.run([docker_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return completed.returncode == 0
    except Exception:
        return False

def remove_existing_container(name: str) -> None:
    docker = shutil.which("docker") or "docker"
    # ignore errors
    subprocess.run([docker, "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def run_container(image: str, name: str, apikey: str, restart_on_failure: int | None) -> int:
    docker = shutil.which("docker") or "docker"
    if restart_on_failure is None:
        restart_arg = None
    else:
        restart_arg = f"on-failure:{restart_on_failure}"

    cmd = [docker, "run", "-d"]
    if restart_arg:
        cmd.append(f"--restart={restart_arg}")
    cmd += ["--name", name, "-e", f"riotapikey={apikey}", image]

    print("Running container.")
    try:
        completed = subprocess.run(cmd)
        return completed.returncode
    except Exception as e:
        print("Error running docker:", e)
        return 2

def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="Run lol_analysis_app container with Riot API key")
    p.add_argument("--apikey", "-k", help="Riot API key to pass to the container")
    p.add_argument("--restart-on-failure", "-r", type=int, default=DEFAULT_RESTART_ON_FAILURE,
                   help=f"Restart on failure retries (default: {DEFAULT_RESTART_ON_FAILURE})")
    p.add_argument("--image", help="Docker image to run", default=DEFAULT_IMAGE)
    p.add_argument("--name", help="Container name", default=DEFAULT_NAME)
    args = p.parse_args(argv)

    inpath = Path("apikey.txt")
    apikey = args.apikey if args.apikey else read_apikey_from_file(inpath)

    if not apikey:
        print("ERROR: Riot API key not provided.")
        print("Provide it via --apikey, in apikey.txt next to this script, or set the riotapikey environment variable.")
        return 1

    print("Using riotapikey:", mask_key(apikey))

    if not check_docker_available():
        print("ERROR: Docker not found in PATH. Please install Docker and ensure 'docker' command is available.")
        return 2

    print("Removing existing container (if any)...")
    remove_existing_container(args.name)

    rc = run_container(args.image, args.name, apikey, args.restart_on_failure)
    if rc != 0:
        print("ERROR: docker run failed with exit code", rc)
        return rc

    print("Container started.")
    return 0


if __name__ == "__main__":
    rc = main()
    input("Press Enter to exit...")
    sys.exit(rc)
