import sql_conn
import pandas as pd
import json

def insert_participants_json_into_table_no_commit(matchID, participant_json, cursor):
    exclude_keys = {"perks", "challenges", "missions"}      # exclude nested dicts
    exclude_keys.add("bountyLevel")                         # random field not in all games?

    # take cols from first participant
    columns = [k for k in participant_json[0].keys() if k not in exclude_keys]  
    column_names = ", ".join(columns)
    placeholders = ", ".join(["?"] * (len(columns) + 1))    # +1 for matchID      

    sql = f"INSERT INTO MatchParticipant (matchID, {column_names}) VALUES ({placeholders})"

    for participant in participant_json:
        values = [participant[col] for col in columns]
        values.insert(0, matchID)                           # insert matchID at the beginning
        cursor.execute(sql, values)

if __name__ == "__main__":
    with open("data/match_example.json", "r") as f:
        example_json = json.load(f)   # this gives a list of dicts

    conn = sql_conn.get_db_connection(False)  # don't autocommit
    cursor = conn.cursor()

    insert_participants_json_into_table_no_commit(
        example_json['metadata']['matchId'], 
        example_json['info']['participants'], 
        cursor)

    # conn.commit()
    cursor.close()
    sql_conn.close_db_connection(conn)