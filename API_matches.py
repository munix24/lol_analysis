from get_api_key import get_api_key
from get_json_retry import get_json_retry

api_key = get_api_key()

# TODO: add pagination
url_matches = "https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{}/ids?start={}&count={}&api_key={}"

def get_matches_API_json_by_puuid(puuid, start: int = 0, count: int = 1):
    """Fetch match IDs for a `puuid` with pagination.

    Parameters:
    - puuid: player UUID
    - start: offset to start from (0-based)
    - count: number of match IDs to return (max 100 per Riot API)
    """
    try:
        s = max(0, int(start))
    except Exception:
        s = 0
    try:
        c = max(1, int(count))
    except Exception:
        c = 100

    _url_matches = url_matches.format(puuid, s, c, api_key)
    matchIDs_list = get_json_retry(_url_matches)
    return matchIDs_list
