from get_env_var import get_env_var
from DB_client_mongo import MongoDBClient

def get_client():
    try:
        db_server_and_port = get_env_var('dbserverandport', required=False)
        db_database = get_env_var('dbdatabase', required=False)
        db_usr = get_env_var('dbusr', required=False)
        db_pwd = get_env_var('dbpwd', required=False)
    except KeyError as e:
        print("Environment variable for database connection is missing: " + str(e))
        raise
    except Exception as e:
        print("Error getting DB environment variables: " + str(e))
        raise
    
    return MongoDBClient(db_server_and_port, db_usr, db_pwd, db_database)

# Create a module-level `db` instance so callers can import `db` directly
# Example: `from DB_client import db`
db = get_client()
