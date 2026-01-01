from get_api_key import get_api_key
from get_json_retry import get_json_retry

url_match = "https://americas.api.riotgames.com/lol/match/v5/matches/{}?api_key={}" 

def get_match_API_json_by_matchID(matchID):
    _url_match = url_match.format(matchID, get_api_key())
    match_json = get_json_retry(_url_match)
    return match_json
