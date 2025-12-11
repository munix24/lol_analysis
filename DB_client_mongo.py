import os
import pandas as pd
from get_env_var import get_env_var
from typing import Any, Dict, List

try:
    import pymongo
except Exception:
    pymongo = None


class MongoDBClient:
    def __init__(self):
        if pymongo is None:
            raise ImportError("pymongo is required for MongoDB backend. Install with 'pip install pymongo'.")
        mongo_uri = get_env_var('mongo_uri', required=False) or os.environ.get('MONGO_URI') or 'mongodb://localhost:27017'
        mongo_dbname = get_env_var('mongo_dbname', required=False) or os.environ.get('MONGO_DBNAME') or 'lol_analysis'
        self.client = pymongo.MongoClient(mongo_uri)
        self.db = self.client[mongo_dbname]

    def get_oldest_ranked_puuids_df(self) -> pd.DataFrame:
        coll = self.db['LeagueV4']
        cursor = coll.find({'queueType': 'RANKED_SOLO_5x5'}, {'puuid': 1, '_id': 0}).sort([('updateMatchesUtc', 1), ('totalGames', -1)])
        docs = list(cursor)
        df = pd.DataFrame(docs)
        return df

    def merge_league_v4(self, leagues_v4_json: List[Dict[str, Any]]):
        coll = self.db['LeagueV4']
        for doc in leagues_v4_json:
            filter_q = {'queueType': doc.get('queueType'), 'puuid': doc.get('puuid')}
            update_doc = {k: v for k, v in doc.items()}
            update_doc['updateRankUtc'] = pd.Timestamp.utcnow().to_pydatetime()
            update_doc['updateMatchesUtc'] = pd.Timestamp.utcnow().to_pydatetime()
            coll.update_one(filter_q, {'$set': update_doc}, upsert=True)

    def begin_transaction(self):
        # For now we don't use multi-document transactions.
        return None

    def commit_transaction(self, txn):
        return None

    def close_transaction(self, txn):
        return None

    def select_matches_in_list_not_in_table(self, matchIDs_list: List[str]) -> List[str]:
        if not matchIDs_list:
            return []
        coll = self.db['Match']
        existing = coll.find({'matchID': {'$in': matchIDs_list}}, {'matchID': 1, '_id': 0})
        existing_ids = {doc['matchID'] for doc in existing}
        return [m for m in matchIDs_list if m not in existing_ids]

    def insert_match_no_commit(self, matchID: str, dataVersion: str, match_info_json: Dict[str, Any], txn=None):
        coll = self.db['Match']
        doc = {'matchID': matchID, 'dataVersion': dataVersion}
        # copy fields except participants/teams
        exclude = {'participants', 'teams', 'gameModeMutators'}
        for k, v in match_info_json.items():
            if k not in exclude:
                doc[k] = v
        coll.insert_one(doc)

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
