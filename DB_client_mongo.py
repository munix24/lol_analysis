import os
import pandas as pd
from get_env_var import get_env_var
from typing import Any, Dict, List

try:
    import pymongo
except Exception:
    pymongo = None

class MongoDBClient:
    def __init__(self, db_usr: str = None, db_pwd: str = None, db_server_and_port: str = None, db_database: str = None):
        if pymongo is None:
            raise ImportError("pymongo is required for MongoDB backend. Install with 'pip install pymongo'.")
        try:
            conn_str = "mongodb://" + db_usr + ":" + db_pwd + "@" + db_server_and_port +  \
                "/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@tzdimi01@"

            self.client = pymongo.MongoClient(conn_str)
            self.db = self.client[db_database]
        except Exception as e:
            print("Error connecting to database: " + str(e))
            raise

    # TODO: mongoDB not fully transactional
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

    def commit_transaction(self, txn):
        """Commit and end the given transaction/session.

        If `txn` is `None` this is a no-op. Exceptions during commit are propagated.
        """
        if not txn:
            return None
        try:
            txn.commit_transaction()
        finally:
            try:
                txn.end_session()
            except Exception:
                pass

    def close_transaction(self, txn):
        """Abort (rollback) and end the given transaction/session.

        If `txn` is `None` this is a no-op.
        """
        if not txn:
            return None
        try:
            # Attempt to abort the transaction. If the txn was already committed
            # or aborted this may raise; we ignore errors and always end the session.
            txn.abort_transaction()
        except Exception:
            pass
        finally:
            try:
                txn.end_session()
            except Exception:
                pass

    def select_oldest_ranked_puuids_df(self) -> pd.DataFrame:
        coll = self.db['LeagueV4']
        cursor = coll.find({'queueType': 'RANKED_SOLO_5x5'}, {'puuid': 1, '_id': 0}).sort([('updateMatchesUtc', 1), ('totalGames', -1)])
        docs = list(cursor)
        df = pd.DataFrame(docs)
        return df

    def select_matches_in_list_not_in_table(self, matchIDs_list: List[str]) -> List[str]:
        if not matchIDs_list:
            return []
        coll = self.db['Match']
        existing = coll.find({'matchID': {'$in': matchIDs_list}}, {'matchID': 1, '_id': 0})
        existing_ids = {doc['matchID'] for doc in existing}
        return [m for m in matchIDs_list if m not in existing_ids]

    def merge_league_v4_no_commit(self, leagues_v4_json: List[Dict[str, Any]], txn=None):
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
            coll.update_one(filter_q, {'$set': update_fields, '$setOnInsert': {'createUtc': now, 'updateMatchesUtc': now}}, upsert=True)

    def merge_league_v4(self, puuid: str, leagues_v4_json: List[Dict[str, Any]]):
        """Upsert league entries for the given `puuid` and update the `updateMatchesUtc` timestamp."""

        self.merge_league_v4_no_commit(leagues_v4_json)

        coll = self.db['LeagueV4']
        now = pd.Timestamp.utcnow().to_pydatetime()
        coll.update_many({'puuid': puuid}, {'$set': {'updateMatchesUtc': now}})

    # participants are part of match document in MongoDB
    def insert_participants_no_commit(self, matchID: str, participant_json: List[Dict[str, Any]], txn=None):
        coll = self.db['MatchParticipant']
        docs = []
        exclude = {'perks', 'challenges', 'missions', 'bountyLevel'}
        for p in participant_json:
            doc = {'matchID': matchID}
            for k, v in p.items():
                if k not in exclude:
                    doc[k] = v
            docs.append(doc)
        if docs:
            coll.insert_many(docs)

    def insert_match_no_commit(self, matchID: str, dataVersion: str, match_info_json: Dict[str, Any], txn=None):
        coll = self.db['Match']
        doc = {'matchID': matchID, 'dataVersion': dataVersion}
        # copy fields except participants/teams
        exclude = {}     # don't exlude in MongoDB
        for k, v in match_info_json.items():
            if k not in exclude:
                doc[k] = v
        
        doc['createdUtc'] = pd.Timestamp.utcnow().to_pydatetime()
        coll.insert_one(doc)
