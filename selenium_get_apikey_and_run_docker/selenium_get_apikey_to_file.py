#!/usr/bin/env python3
"""Open Riot Developer site and retrieve API key using Selenium.

Notes:
- REQUIRES TO BE LOGGED IN BEFOREHAND. Will reuse same firefox profile with log in session otherwise log in returns error

- This script opens a visible browser and navigates to the Riot Developer Console.
- You will likely need to sign in interactively; the script will wait until an API key-like
  string (starting with "RGAPI-") appears in the page source and then saves it.
- Automation of login may be blocked by Riot or require additional steps (MFA). This script
  intentionally leaves login to the user and only automates navigation and scraping.

Usage:
  python docker_get_apikey_selenium.py --outputFileName apikey.txt

Security:
- The script writes the discovered key to the outputFileName file (default: apikey.txt). Keep that file
  protected (chmod 600) and avoid committing it to source control.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import tempfile
import shutil
from pathlib import Path

try:
	from selenium import webdriver
	from selenium.webdriver.common.by import By
	from selenium.webdriver.firefox.options import Options
except Exception:
	webdriver = None

# Default parameters/constants
DEFAULT_OUTPUT_FILE = "apikey.txt"
DEFAULT_TIMEOUT = 30
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_PROFILE_PATH = r"C:\Users\jzsmi\AppData\Roaming\Mozilla\Firefox\Profiles\7mswh3nh.default-release"

def ensure_selenium_available():
	if webdriver is None:
		print("selenium or webdriver not installed. Install with: pip install selenium webdriver-manager")
		sys.exit()

# diagnostics: check if profile path exists and if a Firefox "lock" file indicates it's in use
def check_profile_locks(profile_path: Path) -> list:
	"""Return a list of lock filenames found inside the given Firefox profile directory."""
	lock_files = ("parent.lock", "lock", ".parentlock")
	found = [lf for lf in lock_files if (profile_path / lf).exists()]
	return found

def find_key_in_text(text: str) -> str | None:
	# Riot API keys typically start with RGAPI- followed by hex/characters and dashes
	m = re.search(r"RGAPI-[0-9A-Fa-f\-]{20,}", text)
	if m:
		return m.group(0)
	# fallback: look for long alphanumeric sequences (not ideal)
	# m2 = re.search(r"[A-Za-z0-9\-]{24,}", text)
	# if m2:
	# 	return m2.group(0)
	return None

def create_driver(profile_path: Path | None = None):
	"""Create and return a Selenium Firefox WebDriver.

	If `profile_path` is provided the function will attempt to start Firefox with
	that profile (it must not be in use). Exits the process on failure.
	"""
	try:
		if profile_path:
			print(f"Using Firefox profile path: {profile_path}")
			if not Path(profile_path).exists():
				print("Warning: provided profile path does not exist. Firefox may fail to start with this profile.")
			profile_p = Path(profile_path)
			# found_locks = check_profile_locks(profile_p)
			# if found_locks:
			# 	print(f"Detected lock file(s) in profile directory: {found_locks}")
			# 	print("This usually means Firefox is running with that profile and it cannot be reused directly.")
			# 	print("Close Firefox or provide a copy of the profile directory and retry.")
			# 	sys.exit()

			options = Options()
			options.add_argument("-profile")
			options.add_argument(str(profile_p))
			driver = webdriver.Firefox(options=options)
		else:
			driver = webdriver.Firefox()
		return driver
	except Exception as e:
		print("Failed to start Firefox WebDriver:", e)
		print("ENSURE FIREFOX IS NOT ALREADY RUNNING.")
		print()
		sys.exit()

def navigate_and_find_api(driver, target: str, timeout: int = 300, poll_interval: float = 2.0) -> str | None:
	"""Navigate the given driver to `target` and wait/poll for an RGAPI key in the page source.

	Returns the key string if found, otherwise None.
	"""
	driver.get(target)
	print("If you are not signed in, please sign in in the opened browser window.")
	print("Waiting for API key to appear on the page...")

	start = time.time()
	foundApiKey = None
	while True:
		try:
			src = driver.page_source
		except Exception:
			src = ""
		key = find_key_in_text(src)
		if key:
			foundApiKey = key
			break
		if time.time() - start > timeout:
			break
		time.sleep(poll_interval)

	if not foundApiKey:
		print("API key not found automatically.")
		print("You can (a) finish login in the browser and press Enter here to retry, or (b) cancel.")
		try:
			input("Press Enter after you have logged in and opened the Console page (or Ctrl+C to abort): ")
		except KeyboardInterrupt:
			print('\nAborted by user.')
			return None
		src = driver.page_source
		foundApiKey = find_key_in_text(src)

	return foundApiKey

def run(outputFileName: Path | str = DEFAULT_OUTPUT_FILE, timeout: int = DEFAULT_TIMEOUT, poll_interval: float = DEFAULT_POLL_INTERVAL, profile_path: Path | None = DEFAULT_PROFILE_PATH):
	ensure_selenium_available()
	print("Starting Firefox (creating WebDriver)")

	# create the driver (helper handles profile checks)
	driver = create_driver(profile_path)
	try:
		target = r"https://developer.riotgames.com/"
		print(f"Navigating to {target}")

		# call the navigator that waits/polls the page for an API key
		foundApiKey = navigate_and_find_api(driver, target, timeout=timeout, poll_interval=poll_interval)

		if foundApiKey is None:
			# None signals the user aborted during interactive retry
			return 3
		if not foundApiKey:
			print("Still no API key found. Some Riot pages may hide keys behind JS actions or require explicit clicks.")
			print("You can inspect the Console page and copy the key manually into the outputFileName file.")
			return 4

		print("Found API key:", foundApiKey)
		Path(outputFileName).write_text(foundApiKey, encoding="utf-8")
		print(f"Wrote API key to {outputFileName}")
		return 0
	finally:
		try:
			driver.quit()
		except Exception:
			pass

def main(argv: list[str] | None = None):
	argv = argv if argv is not None else sys.argv[1:]
	p = argparse.ArgumentParser(description="Open Riot Developer Console and retrieve API key using Selenium.")
	p.add_argument("--outputFileName", "-o", default=DEFAULT_OUTPUT_FILE, help=f"File to write the API key to (default: {DEFAULT_OUTPUT_FILE})")
	p.add_argument("--timeout", "-t", type=int, default=DEFAULT_TIMEOUT, help=f"Seconds to wait for key to appear (default: {DEFAULT_TIMEOUT})")
	p.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL, help=f"Seconds between polls while waiting for the key (default: {DEFAULT_POLL_INTERVAL})")
	p.add_argument("--profile-path", "-p", default=DEFAULT_PROFILE_PATH, help="Path to Firefox profile directory to reuse (use a copy of your profile)")
	args = p.parse_args(argv)

	# test profile path
	# profile = Path(args.profile_path) if args.profile_path else r"C:\Users\jzsmi\OneDrive\Desktop\osbpl924.default"
	rc = run(args.outputFileName, args.timeout, args.poll_interval, args.profile_path)
	sys.exit(rc)

if __name__ == '__main__':
	main()

