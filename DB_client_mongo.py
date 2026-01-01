import os
import pandas as pd
from get_env_var import get_env_var
from typing import Any, Dict, List
import time
import ipaddress

try:
    import pymongo
except Exception:
    pymongo = None

class MongoDBClient:
    def __init__(self, db_server_and_port: str = None, db_usr: str = None, db_pwd: str = None, db_database: str = None):
        if pymongo is None:
            raise ImportError("pymongo is required for MongoDB backend. Install with 'pip install pymongo'.")
        try:
            if not db_server_and_port:
                self.client = pymongo.MongoClient("192.168.1.167")     # conn to default localhost:27017
            elif 'localhost' in db_server_and_port.lower():
                self.client = pymongo.MongoClient()     # conn to default localhost:27017
            else:
                conn_str = "mongodb://" + db_usr + ":" + db_pwd + "@" + db_server_and_port +  \
                    "/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@tzdimi01@"
                self.client = pymongo.MongoClient(conn_str)

            if not db_database:
                db_database = 'lol_analysis'

            self.db = self.client[db_database]
            print("Connected to MongoDB server:", db_server_and_port)
            print("Connected to MongoDB db_database:", db_database)
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

    def select_oldest_ranked_puuids_df(self) -> pd.DataFrame:
        coll = self.db['LeagueV4']
        cursor = coll.find(
                    {'queueType': 'RANKED_SOLO_5x5'}, 
                    {'puuid': 1, '_id': 0}).sort([('updateMatchesUtc', 1), ('totalGames', -1)]).limit(100)
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
                {'$set': update_fields, '$setOnInsert': {'createUtc': now, 'updateMatchesUtc': now}}, 
                upsert=True,
                session=session)
            
    def merge_league_v4(self, puuid: str, leagues_v4_json: List[Dict[str, Any]]):
        """Upsert league entries for the given `puuid` and update the `updateMatchesUtc` timestamp."""

        self.merge_league_v4_no_commit(leagues_v4_json)

        coll = self.db['LeagueV4']
        now = pd.Timestamp.utcnow().to_pydatetime()
        coll.update_many({'puuid': puuid}, {'$set': {'updateMatchesUtc': now}})

    # participants are part of match document in MongoDB
    def insert_participants_no_commit(self, matchID: str, participant_json: List[Dict[str, Any]], session=None):
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
            coll.insert_many(docs, session=session)

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
        coll.insert_one(doc, session=session)

    def adhoc_league_v4_merge(self):
        league_collection = self.db["LeagueV4"]
        match_collection = self.db["Match"]

        league_map = {doc["puuid"]: doc for doc in league_collection.find()}
        bulk_ops = []

        for match_doc in match_collection.find():
            updated_participants = []
            for participant in match_doc.get("participants", []):
                puuid = participant.get("puuid")
                league = league_map.get(puuid)
                if league:
                    participant["LeagueV4"] = league  # Embed leagueV4 data
                updated_participants.append(participant)
            # Prepare a bulk update operation
            bulk_ops.append({
                "filter": {"_id": match_doc["_id"]},
                "update": {"$set": {"participants": updated_participants}}
            })

        # Bulk write to update all match documents
        if bulk_ops:
            result = match_collection.bulk_write([
                pymongo.UpdateOne(op["filter"], op["update"])
                for op in bulk_ops
            ])
            print("Modified count:", result.modified_count)

    def select_all_matches(self) -> pd.DataFrame:
        """Return all documents from the `Match` collection as a pandas DataFrame.

        Note: reading an entire collection into memory can be large — consider
        adding a `filter`, `projection` or `limit` parameters if you expect many
        documents.
        """
        coll = self.db['Match']
        cursor = coll.find()
        docs = list(cursor)
        if not docs:
            return pd.DataFrame()
        df = pd.DataFrame(docs)
        # Convert MongoDB ObjectId to string for easier display/usage
        if '_id' in df.columns:
            df['_id'] = df['_id'].apply(str)
        return df
    
    def time_select_matches(self) -> float:
        start = time.perf_counter()
        df = self.select_all_matches()
        elapsed = time.perf_counter() - start

        rows = df.shape[0] if hasattr(df, "shape") else (len(df) if hasattr(df, "__len__") else "unknown")
        print(f"select_matches returned {rows} rows in {elapsed:.3f} s")

        # optional: show a sample
        if hasattr(df, "head"):
            print(df.head())
