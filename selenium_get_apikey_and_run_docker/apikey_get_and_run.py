#!/usr/bin/env python3
"""Wrapper: retrieve Riot API key via Selenium then run the Docker container.

This script first attempts to read `apikey.txt` (or the file given by
`--outputFileName`). If missing or if `--force-get` is provided, it runs
`docker_get_apikey_selenium_to_file.run()` to obtain and write the key.

After a key is present, it calls `docker_run_lol_analysis_app.main()` with
`--apikey <key>` to start the container.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import selenium_get_apikey_to_file as selenium_getter
except Exception:
    selenium_getter = None

try:
    import docker_run_lol_analysis_app as docker_runner
except Exception:
    docker_runner = None

def read_key_from_file(p: Path) -> str | None:
    if not p.exists():
        return None
    try:
        txt = p.read_text(encoding="utf-8").strip()
        return txt or None
    except Exception:
        return None


def get_apikey(args) -> tuple[int, str | None]:
    """Return (rc, apikey). rc==0 means success and apikey is set.

    Uses existing file unless --force-get is set, otherwise runs the selenium helper.
    """
    outpath = Path(args.outputFileName)
    apikey = None if bool(args.force_get) else read_key_from_file(outpath)

    if apikey:
        print(f"Read API key from {args.outputFileName}")
        return 0, apikey

    if selenium_getter is None:
        print("ERROR: selenium retriever module not importable. Ensure file is present and imports succeed.")
        return 2, None

    # Build CLI-style argv and call selenium_getter.main(argv)
    cli_argv: list[str] = ["--outputFileName", str(outpath)]
    if args.timeout is not None:
        cli_argv += ["--timeout", str(args.timeout)]
    if args.poll_interval is not None:
        cli_argv += ["--poll-interval", str(args.poll_interval)]
    if args.profile_path is not None:
        cli_argv += ["--profile-path", str(args.profile_path)]

    print("Retrieving API key via browser (Selenium)...")
    try:
        # selenium_getter.main typically calls sys.exit(rc); capture exit code via SystemExit
        rc = selenium_getter.main(cli_argv)
    except SystemExit as e:
        print("Selenium helper exited with SystemExit:", e)
        code = getattr(e, "code", None)
        rc = 0 if code is None else int(code)
    except Exception as e:
        print("Selenium helper raised an exception:", e)
        return 2, None

    if rc != 0:
        print(f"Selenium retriever finished with exit code {rc}")
        return rc, None

    apikey = read_key_from_file(outpath)
    if not apikey:
        return 1, None
    return 0, apikey


def start_container(apikey: str, args) -> int:
    """Start docker container with given apikey using docker_runner. Returns exit code."""
    if docker_runner is None:
        print("ERROR: docker runner module not importable. Ensure `docker_run_lol_analysis_app.py` is present.")
        return 2

    docker_argv: list[str] = ["--apikey", apikey]
    if args.restart_on_failure:
        docker_argv += ["--restart-on-failure", str(args.restart_on_failure)]
    if args.image:
        docker_argv += ["--image", args.image]
    if args.name:
        docker_argv += ["--name", args.name]

    print("Starting Docker container with retrieved key...")
    try:
        rc2 = docker_runner.main(docker_argv)
    except SystemExit as e:
        print("Docker runner exited with SystemExit:", e)
        code2 = getattr(e, "code", None)
        rc2 = 0 if code2 is None else int(code2)
    except Exception as e:
        print("Docker runner raised an exception:", e)
        return 2

    return int(rc2) if rc2 is not None else 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    p = argparse.ArgumentParser(description="Get Riot API key then run Docker container")
    p.add_argument("--force-get", action="store_true", 
                   help="Always run the Selenium retriever even if the file exists and contains a key")
    p.add_argument("--outputFileName", "-o", default="apikey.txt",
                   help="Optional file to read/write the API key (default: apikey.txt if omitted)")
    p.add_argument("--timeout", type=int, default=None, help="Optional timeout (seconds) to wait for key in browser")
    p.add_argument("--profile-path", default=None, help="Optional Firefox profile path to reuse (use a copy)")
    p.add_argument("--poll-interval", type=float, default=None, help="Optional poll interval (seconds) when waiting for the API key")

    # Docker runner options (passed through to docker_run_lol_analysis_app)
    p.add_argument("--restart-on-failure", type=int, default=None, help="Docker restart on-failure count (optional)")
    p.add_argument("--image", default=None, help="Docker image to run (overrides default if provided)")
    p.add_argument("--name", default=None, help="Container name to use (overrides default if provided)")

    args = p.parse_args(argv)

    # Orchestrate: get API key, then start container
    rc_get, apikey = get_apikey(args)
    if rc_get != 0:
        return rc_get

    rc_run = start_container(apikey, args)
    return rc_run


if __name__ == "__main__":
    rc = main()
    print(f"Finished with exit code {rc}")
    try:
        input("Press Enter to exit...")
    except EOFError:
        pass
    raise SystemExit(rc)
