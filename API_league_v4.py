from get_api_key import get_api_key
from get_json_retry import get_json_retry

api_key = get_api_key()
url_ranked='https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/{}?api_key={}'

def get_league_v4_API_json_by_puuid(puuid):
    _url_ranked=url_ranked.format(puuid, api_key)
    league_v4_json = get_json_retry(_url_ranked)
    return league_v4_json
