import json
import pandas as pd
import sys
from get_api_key import get_api_key
from get_json_retry import get_json_retry

api_key = get_api_key()
url_ranked='https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/{}?api_key={}'

# This module provides Riot API helpers only. DB persistence is handled by the
# DB client modules and orchestrator (`start.py`).

def get_league_v4_API_json_by_puuid(puuid):
    # --- API CALL WITH urllib ---
    _url_ranked=url_ranked.format(puuid, api_key)

    # url = "https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/" + puuid_ptang + "?api_key=" + api_key
    # with urllib.request.urlopen(url) as response:
    #     league_v4_json = json.loads(response.read().decode())   # expecting a list of objects

    league_v4_json = get_json_retry(_url_ranked)
    return league_v4_json

# no DB code here
