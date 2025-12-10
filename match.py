import sql_conn
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

    conn = sql_conn.get_db_connection()
    cursor = conn.cursor()

    # '?' parameter placeholders for the IN clause in query
    placeholders = ','.join('?' for _ in matchIDs_list)
    query = f"SELECT matchId FROM lol_analysis.dbo.Match WHERE matchId IN ({placeholders})"
    cursor.execute(query, matchIDs_list)
    
    matchIDs_existing = {row[0] for row in cursor.fetchall()}

    conn.close()

    # keep only new match IDs
    matchIDs_list_new = [m for m in matchIDs_list if m not in matchIDs_existing]
    return matchIDs_list_new

def insert_match_json_into_table_no_commit(matchID, dataVersion, match_info_json, cursor):
    exclude_keys = {"participants", "teams"}    # exclude nested dicts
    exclude_keys.add("gameModeMutators")        # field only in ARAM

    # keys should map exactly to table columns
    columns = [k for k in match_info_json.keys() if k not in exclude_keys]  
    column_names = ", ".join(columns)
    placeholders = ", ".join(["?"] * (len(columns) + 2))    # +2 for matchID and dataVersion

    sql = f"INSERT INTO Match (matchID, dataVersion, {column_names}) VALUES ({placeholders})"

    values = [match_info_json[col] for col in columns]
    values.insert(0, matchID)                           # insert matchID at the beginning
    values.insert(1, dataVersion)                       # insert dataVersion 
    cursor.execute(sql, values)

if __name__ == "__main__":
    with open("data/match_example.json", "r") as f:
        example_json = json.load(f)   # this gives a list of dicts

    conn = sql_conn.get_db_connection(False)  # don't autocommit
    cursor = conn.cursor()

    insert_match_json_into_table_no_commit(
        example_json['metadata']['matchId'], 
        example_json['metadata']['dataVersion'], 
        example_json['info'], 
        cursor)

    conn.commit()
    cursor.close()
    sql_conn.close_db_connection(conn)