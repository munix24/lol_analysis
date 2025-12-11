from get_api_key import get_api_key
from get_json_retry import get_json_retry

api_key = get_api_key()

# TODO: add pagination
url_matches = "https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{}/ids?start=0&count=100&api_key={}"

def get_matches_API_json_by_puuid(puuid):
    _url_matches = url_matches.format(puuid, api_key)
    matchIDs_list = get_json_retry(_url_matches)
    return matchIDs_list
