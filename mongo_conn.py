from pymongo import MongoClient
from env_util import get_env_var

_client = None
_db = None

def get_db():
    """
    Establishes and returns a MongoDB database handle.
    Uses environment variables MONGO_URI and MONGO_DB.
    Connection is cached for reuse.
    """
    global _client, _db
    
    if _db is not None:
        return _db
    
    try:
        mongo_uri = get_env_var("MONGO_URI", required=True)
        mongo_db_name = get_env_var("MONGO_DB", required=True)
        
        _client = MongoClient(mongo_uri)
        _db = _client[mongo_db_name]
        
        # Verify connection with a ping
        _client.admin.command('ping')
        
        return _db
    except KeyError as e:
        print(f"Environment variable for MongoDB connection is missing: {e}")
        raise
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        raise

def close_db_connection():
    """
    Closes the MongoDB connection.
    """
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
