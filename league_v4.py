import sql_conn
import pyodbc
import json
import pandas as pd
import sys
from get_api_key import get_api_key
from get_json_retry import get_json_retry

api_key = get_api_key()
url_ranked='https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/{}?api_key={}'

def select_oldest_ranked_puuid_from_league_v4_df():
    conn = sql_conn.get_db_connection()

    # --- 1. GET ALL PUUIDS FROM SQL ---
    sql_query = "SELECT puuid FROM lol_analysis.dbo.LeagueV4 \
        where queueType = 'RANKED_SOLO_5x5' \
        order by updateMatchesUtc asc, totalGames desc"

    df = pd.read_sql(sql_query, conn)

    conn.close()
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
    conn = sql_conn.get_db_connection(False)    # don't autocommit
    cursor = conn.cursor()

    sql = """
    MERGE lol_analysis.dbo.LeagueV4 AS target
    USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS src (
        leagueId, queueType, tier, rank, puuid,
        leaguePoints, wins, losses,
        veteran, inactive, freshBlood, hotStreak
    )
    ON  target.queueType = src.queueType
    AND target.puuid = src.puuid

    WHEN MATCHED THEN UPDATE SET
        target.leagueId = src.leagueId,
        target.tier = src.tier,
        target.rank = src.rank,
        target.leaguePoints = src.leaguePoints,
        target.wins = src.wins,
        target.losses = src.losses,
        target.veteran = src.veteran,
        target.inactive = src.inactive,
        target.freshBlood = src.freshBlood,
        target.hotStreak = src.hotStreak,
        target.updateRankUtc = SYSUTCDATETIME(),
        target.updateMatchesUtc = SYSUTCDATETIME()

    WHEN NOT MATCHED THEN INSERT (
        leagueId, queueType, tier, rank, puuid,
        leaguePoints, wins, losses,
        veteran, inactive, freshBlood, hotStreak
    )
    VALUES (
        src.leagueId, src.queueType, src.tier, src.rank, src.puuid,
        src.leaguePoints, src.wins, src.losses,
        src.veteran, src.inactive, src.freshBlood, src.hotStreak
    );
    """

    # uses cursor for performance with multiple inserts/updates otherwise use conn.execute("MERGE ...")
    for league_v4_json in leagues_v4_json:
        cursor.execute(sql, (
            league_v4_json["leagueId"],
            league_v4_json["queueType"],
            league_v4_json["tier"],
            league_v4_json["rank"],
            league_v4_json["puuid"],
            league_v4_json["leaguePoints"],
            league_v4_json["wins"],
            league_v4_json["losses"],
            league_v4_json["veteran"],
            league_v4_json["inactive"],
            league_v4_json["freshBlood"],
            league_v4_json["hotStreak"]
        ))

    conn.commit()
    cursor.close()
    sql_conn.close_db_connection(conn)

def merge_into_league_v4_table_no_commit(league_v4_json, cursor):
    sql = """
    MERGE lol_analysis.dbo.LeagueV4 AS target
    USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS src (
        leagueId, queueType, tier, rank, puuid,
        leaguePoints, wins, losses,
        veteran, inactive, freshBlood, hotStreak
    )
    ON  target.queueType = src.queueType
    AND target.puuid = src.puuid

    WHEN MATCHED THEN UPDATE SET
        target.leagueId = src.leagueId,
        target.tier = src.tier,
        target.rank = src.rank,
        target.leaguePoints = src.leaguePoints,
        target.wins = src.wins,
        target.losses = src.losses,
        target.veteran = src.veteran,
        target.inactive = src.inactive,
        target.freshBlood = src.freshBlood,
        target.hotStreak = src.hotStreak,
        target.updateRankUtc = SYSUTCDATETIME()

    WHEN NOT MATCHED THEN INSERT (
        leagueId, queueType, tier, rank, puuid,
        leaguePoints, wins, losses,
        veteran, inactive, freshBlood, hotStreak
    )
    VALUES (
        src.leagueId, src.queueType, src.tier, src.rank, src.puuid,
        src.leaguePoints, src.wins, src.losses,
        src.veteran, src.inactive, src.freshBlood, src.hotStreak
    );
    """
        
    # uses cursor for performance with multiple inserts/updates otherwise use conn.execute("MERGE ...")
    cursor.execute(sql, (
        league_v4_json["leagueId"],
        league_v4_json["queueType"],
        league_v4_json["tier"],
        league_v4_json["rank"],
        league_v4_json["puuid"],
        league_v4_json["leaguePoints"],
        league_v4_json["wins"],
        league_v4_json["losses"],
        league_v4_json["veteran"],
        league_v4_json["inactive"],
        league_v4_json["freshBlood"],
        league_v4_json["hotStreak"]
    ))

def test_merge_into_league_v4_table():
     get_league_v4_API_and_merge_into_table_by_puuid('PUUID_EXAMPLE_1234567890')

def test2_merge_into_league_v4_table():
     with open("data/league_v4_example.json", "r") as f:
         example_json = json.load(f)   # this gives a list of dicts

     merge_into_league_v4_table(example_json)

def test3_merge_into_league_v4_table():
    with open("data/leagueV4_example.json", "r") as f:
        example_json = json.load(f)   # this gives a list of dicts

    conn = sql_conn.get_db_connection(False)  # don't autocommit
    cursor = conn.cursor()

    merge_into_league_v4_table_no_commit(example_json[0], cursor)

    conn.commit()
    cursor.close()
    sql_conn.close_db_connection(conn)

if __name__ == "__main__":
    test2_merge_into_league_v4_table()