## job has to be repeatable and idempotent
import sql_conn
import league_v4
import match
import match_participant

def is_matchID_after_threshold(matchID, region_prefix = "NA1_", threshold = 5_000_000_000) -> bool:
    try:
        return int(matchID[len(region_prefix):]) > threshold
    except ValueError:
        return False

def get_matches_API_not_in_table_after_threshold_by_puuid(puuid, DEBUG=False):
    matchIDs_list = match.get_matches_API_json_by_puuid(puuid)                          # even if null continue to update puuid
    if DEBUG:
        print('total matchIDs for puuid:', len(matchIDs_list))

    matchIDs_list = [m for m in (matchIDs_list or []) if is_matchID_after_threshold(m)]
    if DEBUG:
        print('total matchIDs above threshold:', len(matchIDs_list))

    matchIDs_list = match.select_matches_in_list_not_in_table(matchIDs_list)            # even if null continue to update puuid
    if DEBUG:
        print('new matchIDs to process:', len(matchIDs_list))
    return matchIDs_list

def lookup_and_process_matches_for_oldest_ranked_puuids(DEBUG=False):
    try:
        while True:
            df_puuids = league_v4.select_oldest_ranked_puuid_from_league_v4_df()
            for puuid in df_puuids['puuid']:
                if DEBUG:
                    print(puuid)

                matchIDs_list = get_matches_API_not_in_table_after_threshold_by_puuid(puuid, DEBUG)
                for matchID in matchIDs_list:
                    if DEBUG:
                        print('processing matchID:', matchID)

                    match_json = match.get_match_API_json_by_matchID(matchID)

                    if match_json['info']['endOfGameResult'] == 'GameComplete':   # skip incomplete games
                        conn = sql_conn.get_db_connection(False)        # don't autocommit
                        cursor = conn.cursor()

                        # df_puuids.to_sql('lol_analysis.dbo.TempOldestRankedPuuids', sql_conn.get_db_connection(), if_exists='replace', index=False)
                        match_participant.insert_participants_json_into_table_no_commit(matchID, match_json['info']['participants'], cursor)

                        for participant in match_json['info']['participants']:
                            if participant['puuid'] != puuid:                      # don't update initial participant leagueV4 yet
                                leagues_v4_json = league_v4.get_league_v4_API_json_by_puuid(participant['puuid'])
                                for league_v4_json in leagues_v4_json:               # ranked / flex queues
                                    league_v4.merge_into_league_v4_table_no_commit(league_v4_json, cursor)
                
                        match.insert_match_json_into_table_no_commit(matchID, match_json['metadata']['dataVersion'], match_json['info'], cursor)

                        conn.commit()
                        cursor.close()
                        sql_conn.close_db_connection(conn)

                league_v4.get_league_v4_API_and_merge_into_table_by_puuid(puuid)
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

if __name__ == "__main__":
    lookup_and_process_matches_for_oldest_ranked_puuids(True)
