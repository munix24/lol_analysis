## job has to be repeatable and idempotent
import API_league_v4
import API_matches
import API_match
import DB_client        

def is_matchID_after_threshold(matchID, region_prefix = "NA1_", threshold = 5_000_000_000) -> bool:
    try:
        return int(matchID[len(region_prefix):]) > threshold
    except ValueError:
        return False

def lookup_and_process_matches_for_oldest_ranked_puuids(DEBUG=False):
    try:
        while True:
            df_puuids = DB_client.db.get_oldest_ranked_puuids_df()
            for puuid in df_puuids['puuid']:
                if DEBUG:
                    print(puuid)
                matchIDs_list = API_matches.get_matches_API_json_by_puuid(puuid)                          # even if null continue to update puuid
                if DEBUG:
                    print('total matchIDs for puuid:', len(matchIDs_list))

                matchIDs_list = [m for m in (matchIDs_list or []) if is_matchID_after_threshold(m)]
                if DEBUG:
                    print('total matchIDs above threshold:', len(matchIDs_list))

                matchIDs_list = DB_client.db.select_matches_in_list_not_in_table(matchIDs_list)            # even if null continue to update puuid
                if DEBUG:
                    print('new matchIDs to process:', len(matchIDs_list))

                for matchID in matchIDs_list:
                    if DEBUG:
                        print('processing matchID:', matchID)

                    match_json = API_match.get_match_API_json_by_matchID(matchID)

                    if match_json['info']['endOfGameResult'] == 'GameComplete':   # skip incomplete games
                        txn = DB_client.db.begin_transaction()
                        try:
                            DB_client.db.insert_participants_no_commit(matchID, match_json['info']['participants'], txn)

                            for participant in match_json['info']['participants']:
                                if participant['puuid'] != puuid:                      # don't update initial participant leagueV4 yet
                                    leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(participant['puuid'])
                                    for league_v4_json in leagues_v4_json:
                                        DB_client.db.merge_league_v4_no_commit(league_v4_json, txn)

                            DB_client.db.insert_match_no_commit(matchID, match_json['metadata']['dataVersion'], match_json['info'], txn)
                            DB_client.db.commit_transaction(txn)
                        finally:
                            DB_client.db.close_transaction(txn)

                # fetch latest league data and persist via DB_client.db client
                leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(puuid)
                DB_client.db.merge_league_v4(puuid, leagues_v4_json)
    except KeyboardInterrupt:
        print("Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

if __name__ == "__main__":
    lookup_and_process_matches_for_oldest_ranked_puuids(True)
