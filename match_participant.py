import mongo_conn
import pandas as pd
import json

def insert_participants_json_into_table_no_commit(matchID, participant_json, bulk_operations=None):
    """
    MongoDB version: adds insert operations to bulk_operations list if provided,
    or executes immediately if bulk_operations is None.
    
    Args:
        matchID: The match ID
        participant_json: List of participant data
        bulk_operations: Optional list to collect bulk operations for batch execution
    """
    db = mongo_conn.get_db()
    collection = db['MatchParticipant']
    
    exclude_keys = {"perks", "challenges", "missions"}      # exclude nested dicts
    exclude_keys.add("bountyLevel")                         # random field not in all games?

    documents = []
    for participant in participant_json:
        doc = {'matchId': matchID}
        for key, value in participant.items():
            if key not in exclude_keys:
                doc[key] = value
        documents.append(doc)
    
    if bulk_operations is not None:
        # Add to bulk operations list for batch execution
        from pymongo import InsertOne
        for doc in documents:
            bulk_operations.append(InsertOne(doc))
    else:
        # Execute immediately
        if documents:
            collection.insert_many(documents)

if __name__ == "__main__":
    with open("data/match_example.json", "r") as f:
        example_json = json.load(f)   # this gives a list of dicts

    # MongoDB version: just call the function directly
    # (no need for cursor/connection management as in SQL version)
    insert_participants_json_into_table_no_commit(
        example_json['metadata']['matchId'], 
        example_json['info']['participants'])