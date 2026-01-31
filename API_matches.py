from get_api_key import get_api_key
from get_json_retry import get_json_retry

api_key = get_api_key()
url_matches = "https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{}/ids?start={}&count={}&api_key={}"

# Module-level constants used to determine whether a matchID is in the desired range
MATCHID_REGION_PREFIX = "NA1_"

def get_matches_API_json_by_puuid(puuid, matchID_threshold: int):
    """Fetch match IDs for a `puuid` by paging through results until either:
    - we exhaust available match IDs, or
    - at least one match ID in a page is after the configured season threshold.

    Returns a list of collected match IDs (may be empty).
    """
    all_ids = []
    start = 0
    page_size = 100

    while True:
        page = get_matches_API_json_by_puuid_paginate(puuid, start=start, count=page_size)
        if not page:
            break
        # Collect only IDs in this page that are after the configured threshold
        recent_ids = [m for m in page if is_matchID_after_threshold(m, matchID_threshold)]
        if recent_ids:
            all_ids.extend(recent_ids)
        else:
            # No IDs in this page are recent => we've paged past the threshold
            break

        # If this page had fewer items than requested, we've reached the threshold
        if len(recent_ids) < page_size:
            break

        start += page_size

    return all_ids

def get_matches_API_json_by_puuid_paginate(puuid, start: int = 0, count: int = 100):
    """Fetch match IDs for a `puuid` with pagination.

    Parameters:
    - puuid: player UUID
    - start: offset to start from (0-based)
    - count: number of match IDs to return (max 100 per Riot API)
    """
    _url_matches = url_matches.format(puuid, start, count, api_key)
    matchIDs_list = get_json_retry(_url_matches)
    # Return raw page of match IDs (no filtering) so the caller can decide when to stop paging
    return matchIDs_list or []

def is_matchID_after_threshold(matchID, matchID_threshold: int) -> bool:
    """Return True if `matchID` (a string like 'NA1_1234567890') is after the threshold.

    This mirrors the previous helper that lived in `start.py` and centralises
    the logic in the API helper module so callers can get already-filtered IDs.
    """
    try:
        return int(matchID[len(MATCHID_REGION_PREFIX):]) > matchID_threshold
    except Exception:
        return False
