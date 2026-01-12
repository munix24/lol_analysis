from get_env_var import get_env_var
from pathlib import Path

def get_api_key():
    """Return Riot API key.

    Preference order:
    1. File named `apikey.txt` in the package directory or current working directory.
    2. Environment variable via `get_env_var("riotapikey")` (required fallback).
    """
    # Check for apikey.txt next to this file
    candidates = [Path(__file__).parent / 'apikey.txt', Path('apikey.txt'), Path('../apikey.txt')]
    for p in candidates:
        try:
            if p.exists() and p.is_file():
                api_key = p.read_text(encoding='utf-8').strip()
                if api_key:
                    return api_key
        except Exception:
            # Ignore file read errors and fall back to env var
            pass

    # Fallback: environment
    return get_env_var("riotapikey", required=True)
