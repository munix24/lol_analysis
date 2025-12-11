#!/usr/bin/env python3
"""
Simple test script to verify MongoDB connectivity and basic operations.
This script requires a MongoDB instance to be running and accessible.

Set environment variables:
    MONGO_URI=mongodb://localhost:27017/
    MONGO_DB=lol_analysis_test
"""

import os
import sys
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mongo_conn
import pandas as pd

def test_connection():
    """Test MongoDB connection"""
    print("Testing MongoDB connection...")
    try:
        db = mongo_conn.get_db()
        print(f"✓ Connected to MongoDB database: {db.name}")
        return True
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        return False

def test_league_v4_operations():
    """Test LeagueV4 collection operations"""
    print("\nTesting LeagueV4 operations...")
    try:
        db = mongo_conn.get_db()
        collection = db['LeagueV4']
        
        # Insert test document
        test_doc = {
            'puuid': 'TEST_PUUID_123',
            'queueType': 'RANKED_SOLO_5x5',
            'tier': 'GOLD',
            'rank': 'II',
            'leagueId': 'test-league-id',
            'leaguePoints': 50,
            'wins': 10,
            'losses': 5,
            'veteran': False,
            'inactive': False,
            'freshBlood': False,
            'hotStreak': False,
            'totalGames': 15,
            'updateRankUtc': datetime.utcnow(),
            'updateMatchesUtc': datetime.utcnow()
        }
        
        # Upsert
        result = collection.update_one(
            {'queueType': test_doc['queueType'], 'puuid': test_doc['puuid']},
            {'$set': test_doc},
            upsert=True
        )
        print(f"✓ Upserted document (matched: {result.matched_count}, modified: {result.modified_count}, upserted: {result.upserted_id is not None})")
        
        # Query
        cursor = collection.find(
            {'queueType': 'RANKED_SOLO_5x5'},
            {'puuid': 1, '_id': 0}
        ).sort([('updateMatchesUtc', 1), ('totalGames', -1)])
        
        results = list(cursor)
        df = pd.DataFrame(results)
        print(f"✓ Query returned {len(df)} documents")
        
        # Cleanup
        collection.delete_one({'puuid': 'TEST_PUUID_123'})
        print("✓ Cleaned up test document")
        
        return True
    except Exception as e:
        print(f"✗ Failed LeagueV4 operations: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_match_operations():
    """Test Match collection operations"""
    print("\nTesting Match operations...")
    try:
        db = mongo_conn.get_db()
        collection = db['Match']
        
        # Insert test document
        test_doc = {
            'matchId': 'TEST_MATCH_123',
            'dataVersion': '2',
            'gameCreation': 1234567890,
            'gameDuration': 1800,
            'gameEndTimestamp': 1234569690
        }
        
        result = collection.insert_one(test_doc)
        print(f"✓ Inserted match document with id: {result.inserted_id}")
        
        # Query
        existing = collection.find({'matchId': {'$in': ['TEST_MATCH_123', 'NONEXISTENT']}}, {'matchId': 1, '_id': 0})
        existing_ids = {doc['matchId'] for doc in existing}
        print(f"✓ Found existing match IDs: {existing_ids}")
        
        # Cleanup
        collection.delete_one({'matchId': 'TEST_MATCH_123'})
        print("✓ Cleaned up test document")
        
        return True
    except Exception as e:
        print(f"✗ Failed Match operations: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("MongoDB Integration Test")
    print("=" * 50)
    
    # Check environment variables
    mongo_uri = os.getenv('MONGO_URI')
    mongo_db = os.getenv('MONGO_DB')
    
    if not mongo_uri or not mongo_db:
        print("ERROR: Required environment variables not set:")
        print("  MONGO_URI: " + ("✓" if mongo_uri else "✗ NOT SET"))
        print("  MONGO_DB: " + ("✓" if mongo_db else "✗ NOT SET"))
        print("\nPlease set these environment variables and try again.")
        sys.exit(1)
    
    print(f"MONGO_URI: {mongo_uri}")
    print(f"MONGO_DB: {mongo_db}")
    print()
    
    # Run tests
    all_passed = True
    all_passed &= test_connection()
    all_passed &= test_league_v4_operations()
    all_passed &= test_match_operations()
    
    # Cleanup
    mongo_conn.close_db_connection()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
