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
import sqlite3
from pathlib import Path

try:
	from selenium import webdriver
	from selenium.webdriver.common.by import By
	from selenium.webdriver.firefox.options import Options
	from selenium.webdriver.support.ui import WebDriverWait
	from selenium.common.exceptions import TimeoutException
except Exception:
	webdriver = None

# Default parameters/constants
DEFAULT_OUTPUT_FILE = "apikey.txt"
DEFAULT_TIMEOUT = 30
DEFAULT_POLL_INTERVAL = 2.0
DEFAULT_PROFILE_PATH = r"C:\Users\jack\AppData\Roaming\Mozilla\Firefox\Profiles\m2svr4b9.default-release"
DEFAULT_PROFILE_PATH = r"C:\Users\jzsmi\AppData\Roaming\Mozilla\Firefox\Profiles\7mswh3nh.default-release"
DEFAULT_COOKIES_ONLY = True

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

def _read_firefox_cookies(profile_path: Path, domain_suffixes: tuple[str, ...]) -> list[dict]:
	"""Read cookies from a Firefox profile's cookies.sqlite, filtering by domain suffixes.

	Returns a list of cookie dicts with keys compatible with Selenium's add_cookie.
	Copies the sqlite DB to a temp file to avoid read locks when Firefox is running.
	"""
	cookies = []
	db_path = profile_path / "cookies.sqlite"
	if not db_path.exists():
		print(f"Firefox cookies DB not found at {db_path}")
		return cookies

	tmp_dir = Path(tempfile.mkdtemp(prefix="ff-cookies-"))
	tmp_db = tmp_dir / "cookies.sqlite"
	try:
		shutil.copy2(db_path, tmp_db)
		conn = sqlite3.connect(tmp_db)
		try:
			cur = conn.cursor()
			# Schema: moz_cookies(name, value, host, path, expiry, lastAccessed, creationTime,
			# isSecure, isHttpOnly, inBrowserElement, sameSite, rawSameSite, schemeMap, ...)
			cur.execute(
				"SELECT name, value, host, path, expiry, isSecure, isHttpOnly, sameSite FROM moz_cookies"
			)
			for name, value, host, path, expiry, is_secure, is_http_only, same_site in cur.fetchall():
				host = host or ""
				# Keep cookies whose host ends with one of the target suffixes
				if any(host.endswith(suf) or host.endswith("." + suf) or host == suf for suf in domain_suffixes):
					c = {
						"name": name,
						"value": value,
						"domain": host,
						"path": path or "/",
						"secure": bool(is_secure or 0),
					}
					# Expiry can be None/0 for session cookies; Selenium expects int seconds if provided
					if expiry and int(expiry) > 0:
						c["expiry"] = int(expiry)
					# Optional attributes; Selenium may accept httpOnly/sameSite but they are not required
					# c["httpOnly"] = bool(is_http_only or 0)
					# Map same_site int (0/1/2) to W3C values if needed; skipping for compatibility
					cookies.append(c)
		finally:
			conn.close()
	except Exception as e:
		print(f"Failed reading cookies from Firefox profile: {e}")
	finally:
		try:
			shutil.rmtree(tmp_dir)
		except Exception:
			pass
	return cookies

def _inject_cookies(driver, base_url: str, cookies: list[dict]):
	"""Navigate to base_url and inject provided cookies, then reload.

	Note: You must be on the target domain before adding cookies for it.
	"""
	if not cookies:
		return
	try:
		driver.get(base_url)
		for c in cookies:
			try:
				driver.add_cookie(c)
			except Exception:
				# Some cookies (e.g., with unsupported attributes) may fail to add; continue
				pass
		driver.get(base_url)
	except Exception as e:
		print(f"Cookie injection failed: {e}")

def create_driver(profile_path: Path | None = None):
	"""Create and return a Selenium Firefox WebDriver.

	If `profile_path` is provided, attempts to start Firefox with that profile (it must not be in use).
	Otherwise starts a clean Firefox session. Cookie injection, if needed, is handled by the caller.
	"""
	try:
		if profile_path:
			print(f"Using Firefox profile path: {profile_path}")
			if not Path(profile_path).exists():
				print("Warning: provided profile path does not exist. Firefox may fail to start with this profile.")
			profile_p = Path(profile_path)
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

def navigate_and_find_api(driver, target: str, timeout: int = 300, poll_interval: float = 2.0, cookies: list[dict] | None = None) -> str | None:
	"""Navigate the given driver to `target`, optionally inject cookies, and wait/poll for an RGAPI key.

	- If `cookies` are provided, they are injected after navigating to the target domain.
	- Returns the key string if found, otherwise None.
	"""
	driver.get(target)
	if cookies:
		print("Injecting cookies to reuse session...")
		_inject_cookies(driver, target, cookies)
		
	print("Waiting for API key to appear on the page...")

	foundApiKey = None
	try:
		foundApiKey = WebDriverWait(driver, timeout, poll_frequency=poll_interval).until(
			lambda d: find_key_in_text(d.page_source)
		)
	except TimeoutException:
		pass

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

def run(outputFileName: Path | str = DEFAULT_OUTPUT_FILE, timeout: int = DEFAULT_TIMEOUT, poll_interval: float = DEFAULT_POLL_INTERVAL, profile_path: Path | None = DEFAULT_PROFILE_PATH, cookies_only: bool = DEFAULT_COOKIES_ONLY):
	ensure_selenium_available()
	print("Starting Firefox (creating WebDriver)")

	# create the driver (helper handles profile start only) and prepare cookies if requested
	cookies: list[dict] | None = None
	if cookies_only:
		driver = create_driver(None)
		if not profile_path or not Path(profile_path).exists():
			print("Warning: --cookies-only enabled but profile path is missing or invalid; proceeding without cookies.")
		else:
			riot_suffixes = ("riotgames.com", "developer.riotgames.com", "auth.riotgames.com")
			cookies = _read_firefox_cookies(Path(profile_path), riot_suffixes)
	else:
		driver = create_driver(profile_path)
	try:
		target = r"https://developer.riotgames.com/"
		print(f"Navigating to {target}")

		# call the navigator that waits/polls the page for an API key
		foundApiKey = navigate_and_find_api(driver, target, timeout=timeout, poll_interval=poll_interval, cookies=cookies)

		if foundApiKey is None:
			# None signals the user aborted during interactive retry
			return 3
		if not foundApiKey:
			print("Still no API key found. Some Riot pages may hide keys behind JS actions or require explicit clicks.")
			print("You can inspect the Console page and copy the key manually into the outputFileName file.")
			return 4

		print("Found API key:", foundApiKey)
		try:
			Path(outputFileName).write_text(foundApiKey, encoding="utf-8")
		except (OSError, PermissionError) as e:
			print(f"Failed to write API key to {outputFileName}: {e}")
			return 5
		
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
	p.add_argument("--cookies-only", action="store_true", default=DEFAULT_COOKIES_ONLY, help="Use only cookies from the Firefox profile (start clean browser)")
	args = p.parse_args(argv)

	# test profile path
	# profile = Path(args.profile_path) if args.profile_path else r"C:\Users\jzsmi\OneDrive\Desktop\osbpl924.default"
	rc = run(args.outputFileName, args.timeout, args.poll_interval, args.profile_path, cookies_only=args.cookies_only)
	return rc

# should work with all default parameters
if __name__ == '__main__':
	rc = main()
	input("Press Enter to exit...")
	sys.exit(rc)

