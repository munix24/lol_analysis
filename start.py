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

GAME_VERSION_PREFIX = ('16',)            # only want V16.1 games.
MATCHID_THRESHOLD = 5_458_700_000       # Should be as limiting as possible to reduce API calls

# filter bad games, otherwise will use up resources querying later
def should_process_match(match_json, queue_id=420, min_duration=500) -> bool:
    try:
        info = match_json.get('info', {})
        if info.get('endOfGameResult', '') != 'GameComplete':       # skip ongoing games?
            logger.info('endOfGameResult) != GameComplete')
            return False
        if info.get('queueId', 0) != queue_id:                     # only ranked solo
            logger.info('queueId != %s', queue_id)
            return False
        if info.get('gameDuration', 0) <= min_duration:         # not earlySurrender
            logger.info('gameDuration <= %s', min_duration)
            return False
        if not info.get('gameVersion', '').startswith(GAME_VERSION_PREFIX):
            logger.info('gameVersion does not start with any of: %s', ', '.join(sorted(GAME_VERSION_PREFIX)))
            return False
        return True
    except Exception as e:
        print("Error occured: ", e)

def lookup_and_process_matches_only():
    try:
        while True:
            df_matches = DB_client.db.select_oldest_matches()
            for participant in df_matches['participants']:
                puuid = participant['puuid']
                logger.info('puuid: %s', puuid)

                matchIDs_list = API_matches.get_matches_API_json_by_puuid(puuid, MATCHID_THRESHOLD)                      # even if null continue to update puuid
                logger.info('total matchIDs for puuid above season threshold: %s', len(matchIDs_list or []))

                matchIDs_list = DB_client.db.select_matches_in_list_not_in_table(matchIDs_list)       # even if null continue to update puuid
                logger.info('new matchIDs not in table: %s', len(matchIDs_list or []))

                for matchID in matchIDs_list:
                    DB_client.db.insert_match_no_commit(matchID, None, None, None)

    except KeyboardInterrupt:
        print("KeyboardInterrupt used. Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

def get_filter_and_insert_puuid_matches(puuid, get_league_v4_API_json = False):
    logger.debug('puuid: %s', puuid)

    matchIDs_list = API_matches.get_matches_API_json_by_puuid(puuid, MATCHID_THRESHOLD)             
    logger.info('total matchIDs for puuid above threshold: %s', len(matchIDs_list or []))

    matchIDs_list = DB_client.db.select_matches_in_list_not_in_table(matchIDs_list)       
    logger.info('new matchIDs not in table: %s', len(matchIDs_list or []))
    logger.info('')

    for matchID in matchIDs_list:
        logger.info('matchID above threshold: %s', matchID)

        match_json = API_match.get_match_API_json_by_matchID(matchID)
        if should_process_match(match_json):   
            try:
                # mongoDB randomly closing transaction? runtime limit?
                # session = DB_client.db.begin_transaction()
                session = None

                if get_league_v4_API_json:
                    for participant_json in match_json['info']['participants']:  # shouldn't be null after gamecomplete
                        if participant_json['puuid'] != puuid and participant_json['puuid'] != 'BOT':                      # don't update initial participant leagueV4 yet
                            leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(participant_json['puuid'])
                            for league_v4_json in leagues_v4_json:
                                if league_v4_json['queueType'] == 'RANKED_SOLO_5x5':
                                    DB_client.db.merge_league_v4_no_commit(league_v4_json, None)
                                    logger.info('processing puuid: %s', participant_json['puuid'])
                else:
                    pass

                logger.info('Inserting matchID: %s', matchID)
                DB_client.db.insert_match_no_commit(matchID, match_json['metadata']['dataVersion'], match_json['info'], None)
                DB_client.db.commit_transaction(session)
            finally:
                DB_client.db.close_transaction(session)
        logger.info('')

def lookup_matches_and_leagues_v4_for_oldest_ranked_puuids(get_league_v4_API_json = False):
    try:
        while True:
            cursor = DB_client.db.select_oldest_ranked_puuids()
            for doc in cursor:
                puuid = doc['puuid']
                get_filter_and_insert_puuid_matches(puuid, get_league_v4_API_json)

                if get_league_v4_API_json:
                    leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(puuid)
                    DB_client.db.merge_league_v4(puuid, leagues_v4_json)
                else:
                    pass
    except KeyboardInterrupt:
        print("KeyboardInterrupt used. Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

def process_oldest_match():
    try:
        while True:
            matches = DB_client.db.select_oldest_matches()
            for match in matches:
                matchID = match['matchID']
                logger.info('processing matchID: %s', matchID)
                logger.info('')

                for participant_json in match['participants']:
                    puuid = participant_json['puuid']
                    get_filter_and_insert_puuid_matches(puuid, get_league_v4_API_json = False)

                    # After processing all participant's matches, update the participant's win / loss / winP
                    # no, just build a query that will calculate it

                DB_client.db.update_MatchesUtc_match(matchID)

    except KeyboardInterrupt:
        print("KeyboardInterrupt used. Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

if __name__ == "__main__":
    # lookup_matches_and_leagues_v4_for_oldest_ranked_puuids()
    process_oldest_match()
