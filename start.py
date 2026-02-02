## job has to be repeatable and idempotent
import os
import logging

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

# filter games on version and matchID
GAME_VERSION_PREFIX = ('16')            # only want V16.1 games.
# GAME_VERSION_PREFIX = ('16.1', '16.2')            # only want V16.1 games.
MATCHID_THRESHOLD = 5_458_750_000       # Should be as limiting as possible to reduce API reqs

# TODO: get skin from spectator.json instead of localhost

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
    """Return (matches_inserted_per_hour, elapsed_str) for the supplied totals and start time."""
    elapsed_seconds = max(1.0, time.time() - start_time)
    hours = elapsed_seconds / 3600.0
    matches_inserted_per_hour = total_inserted / hours if hours > 0 else float(total_inserted)

    return matches_inserted_per_hour, elapsed_seconds

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
    logger.info('\ttotal matchIDs for puuid this season: %s', len(matchIDs_list or []))

    matchIDs_list = DB_client.db.select_matches_in_list_not_in_table(matchIDs_list)       
    logger.info('\tnew matchIDs not in table: %s', len(matchIDs_list or []))

    matches_inserted_count = 0
    participant_inserted_count = 0

    for matchID in matchIDs_list:
        logger.debug('\t\tmatchID: %s', matchID)

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
                
                matches_inserted_count += 1

                # increment win/loss puuids in the inserted match (if present)
                for participant in match_json.get('info', {}).get('participants', []):
                    DB_client.db.increment_participant_win_loss(participant.get('puuid'), participant.get('win') is True)
                    participant_inserted_count += 1
            finally:
                DB_client.db.close_transaction(session)

    API_reqs_count = len(matchIDs_list or []) + 1    # +1 for initial matches req if any      
    return matches_inserted_count, participant_inserted_count, API_reqs_count

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

    Returns a tuple: (matches_inserted_total, API_reqs_total,
    match_inserted_wins_total, match_inserted_losses_total)
    """
    matches_inserted_total = 0
    API_reqs_total = 0

    for participant_json in match_doc.get('participants', []):
        puuid = participant_json.get('puuid')
        matches_inserted_count, participant_inserted_count, API_reqs_count = get_filter_and_insert_puuid_matches(puuid, False)
        matches_inserted_total += int(matches_inserted_count or 0)
        API_reqs_total += int(API_reqs_count or 0)

        DB_client.db.update_MatchesUtc_league_v4(puuid)
        
        logger.info('\tInserted matches: %d', matches_inserted_count)
        # logger.info('\tInserted participants for puuid: %d', participant_inserted_count)
    return matches_inserted_total, API_reqs_total

def process_oldest_match():
    try:
        # Track running totals and start time to compute inserts/hour
        matches_inserted_since_start = 0
        API_reqs_since_start = 0
        start_time = time.time()

        while True:
            oldest_matches_doc_list = DB_client.db.select_oldest_matches()
            for match_doc in oldest_matches_doc_list:
                matchID = match_doc.get('matchID')
                logger.info('matchID %s', matchID)
                
                match_processing_start_time = time.time()
                matches_inserted_total, API_reqs_total = process_match_participants(match_doc)
                matches_per_req = matches_inserted_total / API_reqs_total if API_reqs_total else 0
                match_inserted_per_hour, match_elapsed_seconds = _compute_rate_and_elapsed(matches_inserted_total, match_processing_start_time)

                logger.info('Processed %s in %.0f sec', matchID, match_elapsed_seconds)
                logger.info('inserted %d matches, %d reqs, %.2f mpr', matches_inserted_total, API_reqs_total, matches_per_req)
                
                matches_inserted_since_start += matches_inserted_total
                API_reqs_since_start += int(API_reqs_total or 0)
                matches_inserted_per_hour, elapsed_seconds = _compute_rate_and_elapsed(matches_inserted_since_start, start_time)
                matches_per_req_since_start = matches_inserted_since_start / API_reqs_since_start if API_reqs_since_start else 0
                API_reqs_per_hour = (API_reqs_since_start / (elapsed_seconds / 3600.0)) if elapsed_seconds > 0 else float(API_reqs_since_start)

                logger.info('total: %d matches, %d reqs, %.2f mpr',
                            matches_inserted_since_start, API_reqs_since_start, matches_per_req_since_start)
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
