from get_env_var import get_env_var
from DB_client_mongo import MongoDBClient

def get_client():
    # Decide backend based on `sqlconnstr` content:
    # - If it starts with "Server", use SQL Server
    # - If it equals or starts with "mongo", use MongoDB
    # If `sqlconnstr` is missing or doesn't exist raise error
    try:
        db_server_and_port = get_env_var('dbserverandport', required=True)
        db_database = get_env_var('dbdatabase', required=False)
        db_usr = get_env_var('dbusr', required=False)
        db_pwd = get_env_var('dbpwd', required=False)
    except KeyError as e:
        print("Environment variable for database connection is missing: " + str(e))
        raise
    except Exception as e:
        print("Error getting DB environment variables: " + str(e))
        raise
    if 'mongo' in db_server_and_port.strip().lower():
        return MongoDBClient(db_usr, db_pwd, db_server_and_port, db_database)

# Create a module-level `db` instance so callers can import `db` directly
# Example: `from DB_client import db`
db = get_client()
