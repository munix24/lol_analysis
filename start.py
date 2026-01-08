## job has to be repeatable and idempotent
import os
import logging
from pathlib import Path

# Configure logging from environment variables before importing application modules
# - Else if LOG_LEVEL is set (e.g. INFO, WARNING), use that
_log_level_env = os.getenv('LOG_LEVEL')
if _log_level_env:
    _level = getattr(logging, _log_level_env.upper(), logging.INFO)
else:
    _level = logging.INFO

logging.basicConfig(level=_level, format='%(message)s')
logging.getLogger('pymongo').setLevel(logging.INFO)             # don't flood log with pymongo debug info

# Now import application modules (they will get configured logging)
import API_league_v4
import API_matches
import API_match
import DB_client

logger = logging.getLogger(__name__)
# Announce the configured root logging level so startup logs show it
logger.info("Logging configured; root level=%s", logging.getLevelName(_level))

# 5420859667 is latest gameID of 15.23
def is_matchID_after_threshold(matchID, region_prefix = "NA1_", threshold = 5_421_000_000) -> bool:
    try:
        return int(matchID[len(region_prefix):]) > threshold
    except ValueError:
        return False
          
# filter bad games, otherwise will use up resources querying later
def should_process_match(match_json, queue_id=420, min_duration=500) -> bool:
    try:
        info = match_json.get('info', {})
        if info.get('endOfGameResult') != 'GameComplete':       # skip ongoing games?
            logger.info('endOfGameResult) != GameComplete')
            return False
        if info.get('queueId') != queue_id:                     # only ranked solo
            logger.info('queueId != %s', queue_id)
            return False
        if info.get('gameDuration', 0) <= min_duration:         # not earlySurrender
            logger.info('gameDuration <= %s', min_duration)
            return False
        if not info.get('gameVersion', '').startswith(('15.24', '16.1')):
            logger.info('gameVersion does not start with 15.24 or 16.1: %s', info.get('gameVersion', ''))
            return False
        return True
    except Exception:
        return False

def lookup_and_process_matches_only_for_recent_matches():
    try:
        while True:
            df_matches = DB_client.db.select_oldest_matches()
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

def lookup_matches_and_leagues_v4_for_oldest_ranked_puuids(start: int = 0, count: int = 100):
    try:
        while True:
            cursor = DB_client.db.select_oldest_ranked_puuids(start=start, count=count)
            for doc in cursor:
                puuid = doc['puuid']
                process_puuid(puuid, get_league_v4_API_json = True)

                leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(puuid)
                DB_client.db.merge_league_v4(puuid, leagues_v4_json)
    except KeyboardInterrupt:
        print("KeyboardInterrupt used. Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

def lookup_matches_for_oldest_match_participants():
    try:
        while True:
            cursor = DB_client.db.select_oldest_matches()
            for doc in cursor:
                matchID = doc['matchID']
                logger.info('matchID: %s', matchID)

                for participant in doc['participants']:
                    puuid = participant['puuid']
                    process_puuid(puuid, get_league_v4_API_json = False)

                DB_client.db.update_MatchesUtc_match(matchID)
    except KeyboardInterrupt:
        print("KeyboardInterrupt used. Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

if __name__ == "__main__":
    # lookup_matches_and_leagues_v4_for_oldest_ranked_puuids()
    lookup_matches_for_oldest_match_participants()
