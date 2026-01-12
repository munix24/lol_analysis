import os
import pandas as pd
from get_env_var import get_env_var
from typing import Any, Dict, List
import perf_select_matches
import time
import ipaddress

try:
    import pymongo
except Exception:
    pymongo = None

class MongoDBClient:
    def __init__(self, db_server_and_port: str = None, db_usr: str = None, db_pwd: str = None, db_database: str = 'lol_analysis'):
        if pymongo is None:
            raise ImportError("pymongo is required for MongoDB backend. Install with 'pip install pymongo'.")
        try:
            if 'localhost' in db_server_and_port.lower():
                self.client = pymongo.MongoClient()     # conn to default localhost:27017
            elif db_server_and_port and not db_usr and not db_pwd:
                self.client = pymongo.MongoClient(db_server_and_port)     # conn to local network db
            else:
                conn_str = "mongodb://" + db_usr + ":" + db_pwd + "@" + db_server_and_port +  \
                    "/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@tzdimi01@"
                self.client = pymongo.MongoClient(conn_str)

            self.db = self.client[db_database]
            print("MongoDB server:", db_server_and_port)
            # print("MongoDB db_database:", db_database)
        except Exception as e:
            print("Error connecting to database: " + str(e))
            raise

    def test_connection(self) -> bool:
        """Return True if a simple ping to the MongoDB server succeeds, False otherwise."""
        if pymongo is None:
            return False
        try:
            # simple ping; will raise if server is unreachable or auth fails
            self.client.admin.command('ping')
            return True
        except Exception:
            return False

    # TODO: currently not transactional - pass as session=session on every update/insert
    def begin_transaction(self):
        """Start a client session and begin a transaction.

        Returns a `pymongo.client_session.ClientSession` with an active transaction,
        or `None` if sessions/transactions are not available or could not be started.
        """
        if pymongo is None:
            return None
        # Some deployments (standalone mongod, or emulators) don't support transactions.
        try:
            session = self.client.start_session()
            # start a transaction on the session; if unsupported an exception may be raised
            session.start_transaction()
            return session
        except Exception:
            # Best-effort: if we couldn't start a transaction, ensure session is ended
            try:
                if 'session' in locals() and session is not None:
                    session.end_session()
            except Exception:
                pass
            return None

    def commit_transaction(self, session):
        """Commit and end the given transaction/session.

        If `session` is `None` this is a no-op. Exceptions during commit are propagated.
        """
        if not session:
            return None
        try:
            session.commit_transaction()
        finally:
            try:
                session.end_session()
            except Exception:
                pass

    def close_transaction(self, session):
        """Abort (rollback) and end the given transaction/session.

        If `session` is `None` this is a no-op.
        """
        if not session:
            return None
        try:
            # Attempt to abort the transaction. If the session was already committed
            # or aborted this may raise; we ignore errors and always end the session.
            session.abort_transaction()
        except Exception:
            pass
        finally:
            try:
                session.end_session()
            except Exception:
                pass

    def select_oldest_ranked_puuids(self):
        coll = self.db['LeagueV4']
        # Exclude documents where updateMatchesUtc is missing or null so sorting behaves predictably
        query = {
            'queueType': 'RANKED_SOLO_5x5',
            'updateMatchesUtc': {'$exists': True, '$ne': None}
        }
        cursor = coll.find(query, {'puuid': 1, '_id': 0}) \
                     .sort([('updateMatchesUtc', 1), ('totalGames', -1)]) \
                     .limit(100)
        # doc_list = list(cursor)
        # df = pd.DataFrame(doc_list)
        return cursor

    def select_oldest_matches(self):
        coll = self.db['Match']
        # Exclude documents where gameCreation is missing or null so sorting behaves predictably
        query = {
            'updateMatchesUtc': {'$exists': True, '$ne': None},
            # '$expr': {'$eq': ['$updateMatchesUtc', '$createdUtc']}  # only matches not yet processed
        }
        projection = {'matchID': 1, 'updateMatchesUtc': 1, 'participants': 1, '_id': 0}
        # Get most recent matches by gameCreation (descending). Adjust limit as needed.
        cursor = coll.find(query, projection).sort([('updateMatchesUtc', 1)]).limit(1)
        # docs = list(cursor)
        return cursor

    def update_match_updateMatchesUtc(self, matchID: str):
        coll = self.db['Match']
        now = pd.Timestamp.utcnow().to_pydatetime()
        coll.update_many({'matchID': matchID}, {'$set': {'updateMatchesUtc': now}})

    def select_matches_in_list_not_in_table(self, matchIDs_list: List[str]) -> List[str]:
        if not matchIDs_list:
            return []
        coll = self.db['Match']
        existing = coll.find({'matchID': {'$in': matchIDs_list}}, {'matchID': 1, '_id': 0})
        existing_ids = {doc['matchID'] for doc in existing}
        return [m for m in matchIDs_list if m not in existing_ids]

    def merge_league_v4_no_commit(self, leagues_v4_json: List[Dict[str, Any]], session=None):
        """Upsert league entries for the given `puuid` and update the `updateMatchesUtc` timestamp.

        Accepts either a single league dict or a list of league dicts in `leagues_v4_json`.
        """
        if not leagues_v4_json:
            return

        coll = self.db['LeagueV4']
        now = pd.Timestamp.utcnow().to_pydatetime()
        leagues_v4_json = leagues_v4_json if isinstance(leagues_v4_json, list) else [leagues_v4_json]
        
        for doc in leagues_v4_json:
            filter_q = {'queueType': doc.get('queueType'), 'puuid': doc.get('puuid')}
            update_fields = {k: v for k, v in doc.items()}
            update_fields['totalGames'] = doc.get('wins', 0) + doc.get('losses', 0)
            update_fields['updateRankUtc'] = now
            # Use $setOnInsert to preserve a createUtc only on insert
            coll.update_one(
                filter_q, 
                {'$set': update_fields, '$setOnInsert': {'createUtc': now}}, 
                upsert=True,
                session=session)
            
    def merge_league_v4(self, puuid: str, leagues_v4_json: List[Dict[str, Any]]):
        """Upsert league entries for the given `puuid` and update the `updateMatchesUtc` timestamp."""
        self.merge_league_v4_no_commit(leagues_v4_json)
        self.update_MatchesUtc_league_v4(puuid)

    def update_MatchesUtc_league_v4(self, puuid: str):
        coll = self.db['LeagueV4']
        now = pd.Timestamp.utcnow().to_pydatetime()
        coll.update_many({'puuid': puuid}, {'$set': {'updateMatchesUtc': now}})

    def dict_exclude_keys(self, data: Dict[str, Any], exclude: set) -> Dict[str, Any]:
        """Return a new dictionary excluding the specified keys."""
        return {k: v for k, v in data.items() if k not in exclude}

    # participants are part of match document in MongoDB
    def insert_participant_no_commit(self, matchID: str, dataVersion: str, match_info_json: Dict[str, Any], participant_json: List[Dict[str, Any]], session=None):
        coll = self.db['Participant']
        # Merge all keys from match_info_json except 'participants' into each participant entry
        doc = {'matchID': matchID, 'dataVersion': dataVersion}
        match_info_json_exclude_participants = self.dict_exclude_keys(match_info_json, {'participants'})
        participant_json_exclude = self.dict_exclude_keys(participant_json, {'perks', 'challenges', 'missions', 'bountyLevel'})

        doc.update(match_info_json_exclude_participants)
        doc.update(participant_json_exclude)
        
        # exclude = {'perks', 'challenges', 'missions', 'bountyLevel'}
        # for k, v in participant_json.items():
        #     if k not in exclude:
        #         doc[k] = v
        coll.insert_one(doc, session=session)

    def insert_match_no_commit(self, matchID: str, dataVersion: str, match_info_json: Dict[str, Any], session=None):
        coll = self.db['Match']
        doc = {'matchID': matchID, 'dataVersion': dataVersion}
        
        match_exclude = {''}     # challenges explode document size
        participant_exclude = {'challenges'}
        for k, v in match_info_json.items():
            if k == 'participants' and isinstance(v, list):
                sanitized = []
                for p in v:
                    if isinstance(p, dict):
                        sanitized.append({pk: pv for pk, pv in p.items() if pk not in participant_exclude})
                    else:
                        sanitized.append(p)
                doc['participants'] = sanitized
            else:
                if k not in match_exclude:
                    doc[k] = v
        
        doc['createdUtc'] = pd.Timestamp.utcnow().to_pydatetime()
        doc['updateMatchesUtc'] = pd.Timestamp.utcnow().to_pydatetime()
        coll.insert_one(doc, session=session)

    def update_participant_win_loss_totalGames(self, puuid, wins, losses, totalGames):
        coll = self.db['LeagueV4']
        now = pd.Timestamp.utcnow().to_pydatetime()
        
        filter_q = {'puuid': puuid}
        update_fields = {'wins': wins, 'losses': losses, 'totalGames': totalGames, 'updateMatchesUtc': now}
        
        coll.update_one(
            filter_q, 
            {'$set': update_fields, '$setOnInsert': {'createUtc': now}}, 
            upsert=True)

    def increment_participant_win_loss(self, puuid, win_bool: bool):
        """Increment wins or losses for `puuid` by 1 based on `win_bool`.

        Reads current `wins`/`losses` values, computes new totals, and writes
        them back. If the document doesn't exist it will be created with
        `createUtc` set.
        """
        try:
            coll = self.db['LeagueV4']
            now = pd.Timestamp.utcnow().to_pydatetime()

            filter_q = {'puuid': puuid}
            existing = coll.find_one(filter_q, {'wins': 1, 'losses': 1})

            existing_wins = int(existing.get('wins', 0)) if existing else 0
            existing_losses = int(existing.get('losses', 0)) if existing else 0

            if win_bool:
                new_wins = existing_wins + 1
                new_losses = existing_losses
            else:
                new_wins = existing_wins
                new_losses = existing_losses + 1

            totalGames = new_wins + new_losses

            update_fields = {
                'wins': new_wins,
                'losses': new_losses,
                'totalGames': totalGames
            }

            coll.update_one(filter_q, {'$set': update_fields, '$setOnInsert': {'createUtc': now, 'updateMatchesUtc': now}}, upsert=True)
        except Exception:
            try:
                import logging
                logging.getLogger(__name__).exception('Failed updating win/loss totals for puuid %s', puuid)
            except Exception:
                pass
