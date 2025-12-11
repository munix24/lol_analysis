import mongo_conn
import json
import pandas as pd
from datetime import datetime
from get_api_key import get_api_key
from get_json_retry import get_json_retry

api_key = get_api_key()
url_ranked='https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/{}?api_key={}'

def select_oldest_ranked_puuid_from_league_v4_df():
    db = mongo_conn.get_db()
    collection = db['LeagueV4']
    
    # Query MongoDB for documents with queueType == 'RANKED_SOLO_5x5'
    # Sort by updateMatchesUtc asc, then totalGames desc
    cursor = collection.find(
        {'queueType': 'RANKED_SOLO_5x5'},
        {'puuid': 1, '_id': 0}
    ).sort([('updateMatchesUtc', 1), ('totalGames', -1)])
    
    # Convert to pandas DataFrame
    results = list(cursor)
    df = pd.DataFrame(results)
    
    return df

def get_league_v4_API_and_merge_into_table_by_puuid(puuid):
    league_v4_json = get_league_v4_API_json_by_puuid(puuid)
    merge_into_league_v4_table(league_v4_json)

def get_league_v4_API_json_by_puuid(puuid):
    # --- API CALL WITH urllib ---
    _url_ranked=url_ranked.format(puuid, api_key)

    # url = "https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/" + puuid_ptang + "?api_key=" + api_key
    # with urllib.request.urlopen(url) as response:
    #     league_v4_json = json.loads(response.read().decode())   # expecting a list of objects

    league_v4_json = get_json_retry(_url_ranked)
    return league_v4_json

def merge_into_league_v4_table(leagues_v4_json):
    db = mongo_conn.get_db()
    collection = db['LeagueV4']
    
    for league_v4_json in leagues_v4_json:
        # Calculate totalGames for sorting
        total_games = league_v4_json.get("wins", 0) + league_v4_json.get("losses", 0)
        
        # Upsert using queueType and puuid as the unique filter
        filter_doc = {
            'queueType': league_v4_json['queueType'],
            'puuid': league_v4_json['puuid']
        }
        
        update_doc = {
            '$set': {
                'leagueId': league_v4_json['leagueId'],
                'tier': league_v4_json['tier'],
                'rank': league_v4_json['rank'],
                'leaguePoints': league_v4_json['leaguePoints'],
                'wins': league_v4_json['wins'],
                'losses': league_v4_json['losses'],
                'veteran': league_v4_json['veteran'],
                'inactive': league_v4_json['inactive'],
                'freshBlood': league_v4_json['freshBlood'],
                'hotStreak': league_v4_json['hotStreak'],
                'totalGames': total_games,
                'updateRankUtc': datetime.utcnow(),
                'updateMatchesUtc': datetime.utcnow()
            }
        }
        
        collection.update_one(filter_doc, update_doc, upsert=True)

def merge_into_league_v4_table_no_commit(league_v4_json, bulk_operations=None):
    """
    MongoDB version: adds upsert operation to bulk_operations list if provided,
    or executes immediately if bulk_operations is None.
    
    Note: This function updates only updateRankUtc, NOT updateMatchesUtc.
    The updateMatchesUtc field is updated only for the primary puuid being processed
    (via merge_into_league_v4_table) after all its matches are processed.
    For other participants found within matches, we only update their rank data.
    
    Args:
        league_v4_json: The league v4 data to upsert
        bulk_operations: Optional list to collect bulk operations for batch execution
    """
    db = mongo_conn.get_db()
    collection = db['LeagueV4']
    
    # Calculate totalGames for sorting
    total_games = league_v4_json.get("wins", 0) + league_v4_json.get("losses", 0)
    
    # Upsert using queueType and puuid as the unique filter
    filter_doc = {
        'queueType': league_v4_json['queueType'],
        'puuid': league_v4_json['puuid']
    }
    
    update_doc = {
        '$set': {
            'leagueId': league_v4_json['leagueId'],
            'tier': league_v4_json['tier'],
            'rank': league_v4_json['rank'],
            'leaguePoints': league_v4_json['leaguePoints'],
            'wins': league_v4_json['wins'],
            'losses': league_v4_json['losses'],
            'veteran': league_v4_json['veteran'],
            'inactive': league_v4_json['inactive'],
            'freshBlood': league_v4_json['freshBlood'],
            'hotStreak': league_v4_json['hotStreak'],
            'totalGames': total_games,
            'updateRankUtc': datetime.utcnow()
        }
    }
    
    if bulk_operations is not None:
        # Add to bulk operations list for batch execution
        from pymongo import UpdateOne
        bulk_operations.append(UpdateOne(filter_doc, update_doc, upsert=True))
    else:
        # Execute immediately
        collection.update_one(filter_doc, update_doc, upsert=True)

def test_merge_into_league_v4_table():
     get_league_v4_API_and_merge_into_table_by_puuid('PUUID_EXAMPLE_1234567890')

def test2_merge_into_league_v4_table():
     with open("data/league_v4_example.json", "r") as f:
         example_json = json.load(f)   # this gives a list of dicts

     merge_into_league_v4_table(example_json)

def test3_merge_into_league_v4_table():
    with open("data/leagueV4_example.json", "r") as f:
        example_json = json.load(f)   # this gives a list of dicts

    # MongoDB version: just call the function directly
    # (no need for cursor management as in SQL version)
    merge_into_league_v4_table_no_commit(example_json[0])

if __name__ == "__main__":
    test2_merge_into_league_v4_table()