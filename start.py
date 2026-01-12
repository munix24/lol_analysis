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
import time

logger = logging.getLogger(__name__)
# Announce the configured root logging level so startup logs show it
logger.info("Logging configured; root level=%s", logging.getLevelName(_level))

GAME_VERSION_PREFIX = ('16.1', '16.2')            # only want V16.1 games.
MATCHID_THRESHOLD = 5_458_750_000       # Should be as limiting as possible to reduce API calls

# filter bad games, otherwise will use up resources querying later
def should_insert_match(match_json, queue_id=420, min_duration=500) -> bool:
    try:
        if not match_json:
            logger.debug('\t\tmatch_json not found')
            return False
        
        info = match_json.get('info', {})
        if info.get('endOfGameResult', '') != 'GameComplete':       # skip ongoing games?
            logger.debug('\t\tendOfGameResult) != GameComplete')
            return False
        if info.get('queueId', 0) != queue_id:                     # only ranked solo
            logger.debug('\t\tqueueId != %s', queue_id)
            return False
        if info.get('gameDuration', 0) <= min_duration:         # not earlySurrender
            logger.debug('\t\tgameDuration <= %s', min_duration)
            return False
        if not info.get('gameVersion', '').startswith(GAME_VERSION_PREFIX):
            logger.debug('\t\tgameVersion does not start with any of: %s', ', '.join(sorted(GAME_VERSION_PREFIX)))
            return False
        return True
    except Exception as e:
        print("Error occured: ", e)

def _compute_rate_and_elapsed(total_inserted: int, start_time: float):
    """Return (inserts_per_hour, elapsed_str) for the supplied totals and start time."""
    elapsed_seconds = max(1.0, time.time() - start_time)
    hours = elapsed_seconds / 3600.0
    inserts_per_hour = total_inserted / hours if hours > 0 else float(total_inserted)

    return inserts_per_hour, elapsed_seconds

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
    logger.debug('\tpuuid: %s', puuid)

    matchIDs_list = API_matches.get_matches_API_json_by_puuid(puuid, MATCHID_THRESHOLD)  
    logger.info('\ttotal matchIDs for puuid above threshold: %s', len(matchIDs_list or []))

    matchIDs_list = DB_client.db.select_matches_in_list_not_in_table(matchIDs_list)       
    logger.info('\tnew matchIDs not in table: %s', len(matchIDs_list or []))

    inserted_match_count = 0
    inserted_participant_count = 0

    for matchID in matchIDs_list:
        logger.debug('\t\tmatchID above threshold: %s', matchID)

        match_json = API_match.get_match_API_json_by_matchID(matchID)
        if should_insert_match(match_json):   
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

                logger.debug('\t\tInserting matchID: %s', matchID)
                DB_client.db.insert_match_no_commit(matchID, match_json['metadata']['dataVersion'], match_json['info'], None)
                DB_client.db.commit_transaction(session)
                
                inserted_match_count += 1

                # increment win/loss puuids in the inserted match (if present)
                for participant in match_json.get('info', {}).get('participants', []):
                    DB_client.db.increment_participant_win_loss(participant.get('puuid'), participant.get('win') is True)
                    inserted_participant_count += 1
            finally:
                DB_client.db.close_transaction(session)

    API_reqs_count = len(matchIDs_list or []) + 1    # +1 for initial matches call if any      
    return inserted_match_count, inserted_participant_count, API_reqs_count

def lookup_matches_and_leagues_v4_for_oldest_ranked_puuids(get_league_v4_API_json = False):
    try:
        while True:
            LeagueV4_json_list = DB_client.db.select_oldest_ranked_puuids()
            for LeagueV4_json in LeagueV4_json_list:
                puuid = LeagueV4_json['puuid']
                get_filter_and_insert_puuid_matches(puuid, get_league_v4_API_json)

                if get_league_v4_API_json:
                    leagues_v4_json = API_league_v4.get_league_v4_API_json_by_puuid(puuid)
                    DB_client.db.merge_league_v4(puuid, leagues_v4_json)
    except KeyboardInterrupt:
        print("KeyboardInterrupt used. Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

def process_match_participants(match_doc):
    """Process participants for a single match JSON.

    Returns a tuple: (match_inserted_total, total_API_calls_for_match,
    match_inserted_wins_total, match_inserted_losses_total)
    """
    match_inserted_total = 0
    total_API_calls_for_match = 0

    for participant_json in match_doc.get('participants', []):
        puuid = participant_json.get('puuid')
        inserted_matches_count, inserted_participant_count, API_reqs_count = get_filter_and_insert_puuid_matches(puuid, False)
        logger.info('\tInserted matches for puuid: %d', inserted_matches_count)
        # logger.info('\tInserted participants for puuid: %d', inserted_participant_count)
        match_inserted_total += int(inserted_matches_count or 0)
        total_API_calls_for_match += int(API_reqs_count or 0)

    return (match_inserted_total, total_API_calls_for_match)

def process_oldest_match():
    try:
        # Track running totals and start time to compute inserts/hour
        total_inserted_since_start = 0
        start_time = time.time()

        while True:
            oldest_matches_doc_list = DB_client.db.select_oldest_matches()
            for match_doc in oldest_matches_doc_list:
                matchID = match_doc.get('matchID')
                logger.info('matchID %s', matchID)
                
                (match_inserted_total, total_api_calls_for_match) = process_match_participants(match_doc)
                matches_per_call = match_inserted_total / total_api_calls_for_match if total_api_calls_for_match else 0
                logger.info('Inserted %d matches in %d calls, %.02f mpc', match_inserted_total, total_api_calls_for_match, matches_per_call)

                total_inserted_since_start += match_inserted_total
                inserts_per_hour, elapsed_seconds = _compute_rate_and_elapsed(total_inserted_since_start, start_time)
                logger.info('Inserted %d matches in %.0f sec, %.0f mph', total_inserted_since_start, elapsed_seconds, inserts_per_hour)
                logger.info('')

                DB_client.db.update_match_updateMatchesUtc(matchID)

    except KeyboardInterrupt:
        print("KeyboardInterrupt used. Shutting down...")
    except Exception as e:
        print("Error occured: ", e)
        raise

if __name__ == "__main__":
    # lookup_matches_and_leagues_v4_for_oldest_ranked_puuids()
    process_oldest_match()
