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
            df_puuids = DB_client.db.select_oldest_ranked_puuids_df()
            for puuid in df_puuids['puuid']:
                if DEBUG:
                    print(puuid)
                matchIDs_list = API_matches.get_matches_API_json_by_puuid(puuid)                      # even if null continue to update puuid
                if DEBUG:
                    print('total matchIDs for puuid:', len(matchIDs_list))

                matchIDs_list = [m for m in (matchIDs_list or []) if is_matchID_after_threshold(m)]
                if DEBUG:
                    print('total matchIDs above threshold:', len(matchIDs_list))

                matchIDs_list = DB_client.db.select_matches_in_list_not_in_table(matchIDs_list)       # even if null continue to update puuid
                if DEBUG:
                    print('new matchIDs to process:', len(matchIDs_list))

                for matchID in matchIDs_list:
                    if DEBUG:
                        print('processing matchID:', matchID)

                    match_json = API_match.get_match_API_json_by_matchID(matchID)

                    if match_json['info']['endOfGameResult'] == 'GameComplete':   # skip incomplete games
                        try:
                            txn = DB_client.db.begin_transaction()

                            # Only insert participants in SQL. MongoDB participants are part of match document
                         if not info.get('gameVersion', '').startswith(('15.24', '16.1')):
            logger.info('gameVersion does not start with 15.24 or 16.1: %s', info.get('gameVersion', ''))
            return False
           if DB_client.db.__class__.__name__ == 'SqlDBClient':

def lookup_and_process_matches_for_orecent_matches()n
    try:
        while True:
            df_matches = DB_client.db.select_most_recent_matches()
            for participant in df_matches['participants']:
                puuid = participant['puuid']
                logger.info('puuid: %s', puuid)

                matchIDs_list = API_matches.get_matches_API_json_by_puuid(puuid)                      # even if null continue to update puuid
                logger.info('total matchIDs for puuid: %s', len(matchIDs_list or []))

                # only want V15.24 games
                matchIDs_list = [m for m in (matchIDs_list or []) if is_matchID_after_threshold(m)]
                logger.info('total matchIDs above threshold: %s', len(matchIDs_list))

                matchIDs_list = DB_client.db.select_matches_in_list_not_in_table(matchIDs_list)       # even if null continue to update puuid
                logger.info('new matchIDs not in table: %s', len(matchIDs_list or []))

                for matchID in matchIDs_list:
                    DB_client.db.insert_match_no_commit(matchID, None, None, None)
    except KeyboardInterrupt:
        print("KeyboardInterrupt used. Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

def process_puuid(puuid, get_league_v4_API_json):
    logger.info('puuid: %s', puuid)

    matchIDs_list = API_matches.get_matches_API_json_by_puuid(puuid)                      # even if null continue to update puuid
    logger.info('total matchIDs for puuid: %s', len(matchIDs_list or []))

    # only want V15.24 games
    matchIDs_list = [m for m in (matchIDs_list or []) if is_matchID_after_threshold(m)]
    logger.info('total matchIDs above threshold: %s', len(matchIDs_list))

    matchIDs_list = DB_client.db.select_matches_in_list_not_in_table(matchIDs_list)       # even if null continue to update puuid
    logger.info('new matchIDs not in table: %s', len(matchIDs_list or []))

    for matchID in matchIDs_list:
        logger.info('processing matchID: %s', matchID)

        match_json = API_match.get_match_API_json_by_matchID(matchID)
        if should_process_match(match_json):   
            try:
                # mongoDB randomly closing transaction? runtime limit?
                # session = DB_client.db.begin_transaction()
                session = None

                if get_league_v4_API_json:
                    for participant in match_json['info']['participants']:  # shouldn't be null after gamecomplete
                        if participant['puuid'] != puuid and participant['puuid'] != 'BOT':                      # don't update initial participant leagueV4 yet
                            leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(participant['puuid'])
                            for league_v4_json in leagues_v4_json:
                                if league_v4_json['queueType'] == 'RANKED_SOLO_5x5':
                                    DB_client.db.merge_league_v4_no_commit(league_v4_json, None)
                                    logger.info('processing puuid: %s', participant['puuid'])

                DB_client.db.insert_match_no_commit(matchID, match_json['metadata']['dataVersion'], match_json['info'], None)
                DB_client.db.commit_transaction(session)
            finally:
                DB_client.db.close_transaction(session)

def lookup_matches_and_leagues_v4_for_oldest_ranked_puuids():ts_no_commit(matchID, match_json['info']['parcursor'], txn)

                         puuids(tic            for doc in cursor:
                puuid = doc['puuid']
                process_puuid(puuid, get_league_v4_API_json = True)
nk                leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(puuid)y:                DB_client.db.merge_league_v4(puuid, leagues_v4_json)puuid(puuid, get_league_v4_API_json)

                if get_league_v4_API_json:
                    leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(puuid)
         B_client.db.merge_league_v4(puuid, leagues_v4_json)
                el
            cursor = DB_client.db.select_most_recent_matches()
            for doc in cursor:
                matchID = doc['matchID']
                logger.info('matchID: %s', matchID)
                for participant in doc['participants']:
                    puuid = participant['puuid']t(                    pt used. Shutting dowget_league_v4_API_json = Falseept                lookup_matches_update_MatchesUtc_matchamatchIDpuuids
    lookup_matches_for_recent_match_participants())# # # # 