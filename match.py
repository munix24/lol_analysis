import mongo_conn
import pandas as pd
import sys
import json
from get_api_key import get_api_key
from get_json_retry import get_json_retry

api_key = get_api_key()

# TODO: add pagination
url_matches = "https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{}/ids?start=0&count=100&api_key={}"
url_match="https://americas.api.riotgames.com/lol/match/v5/matches/{}?api_key={}"

def get_matches_API_json_by_puuid(puuid):
    _url_matches = url_matches.format(puuid, api_key)
    matchIDs_list = get_json_retry(_url_matches)
    # print(_url_matches)
    # print(matchIDs_list)
    return matchIDs_list

def get_match_API_json_by_matchID(matchID):
    _url_match = url_match.format(matchID, api_key)
    match_json = get_json_retry(_url_match)
    # print(_url_match)
    # print(match_json)
    return match_json

def select_matches_in_list_not_in_table(matchIDs_list):
    if not matchIDs_list:
        return []

    db = mongo_conn.get_db()
    collection = db['Match']
    
    # Query MongoDB for matchIds that exist in the database
    cursor = collection.find(
        {'matchId': {'$in': matchIDs_list}},
        {'matchId': 1, '_id': 0}
    )
    
    matchIDs_existing = {doc['matchId'] for doc in cursor}
    
    # keep only new match IDs
    matchIDs_list_new = [m for m in matchIDs_list if m not in matchIDs_existing]
    return matchIDs_list_new

def insert_match_json_into_table_no_commit(matchID, dataVersion, match_info_json, bulk_operations=None):
    """
    MongoDB version: adds insert operation to bulk_operations list if provided,
    or executes immediately if bulk_operations is None.
    
    Args:
        matchID: The match ID
        dataVersion: The data version
        match_info_json: The match info data
        bulk_operations: Optional list to collect bulk operations for batch execution
    """
    db = mongo_conn.get_db()
    collection = db['Match']
    
    exclude_keys = {"participants", "teams"}    # exclude nested dicts
    exclude_keys.add("gameModeMutators")        # field only in ARAM

    # Build document from match_info_json, excluding nested structures
    doc = {
        'matchId': matchID,
        'dataVersion': dataVersion
    }
    
    for key, value in match_info_json.items():
        if key not in exclude_keys:
            doc[key] = value
    
    if bulk_operations is not None:
        # Add to bulk operations list for batch execution
        from pymongo import InsertOne
        bulk_operations.append(InsertOne(doc))
    else:
        # Execute immediately
        collection.insert_one(doc)

if __name__ == "__main__":
    with open("data/match_example.json", "r") as f:
        example_json = json.load(f)   # this gives a list of dicts

    # MongoDB version: just call the function directly
    # (no need for cursor/connection management as in SQL version)
    insert_match_json_into_table_no_commit(
        example_json['metadata']['matchId'], 
        example_json['metadata']['dataVersion'], 
        example_json['info'])