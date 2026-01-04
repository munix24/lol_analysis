from get_env_var import get_env_var
from DB_client_mongo import MongoDBClient

def get_client():
    try:
        db_server_and_port = get_env_var('dbserverandport', required=True)
        db_usr = get_env_var('dbusr', required=False)
        db_pwd = get_env_var('dbpwd', required=False)
        db_database = get_env_var('dbdatabase', required=False)
    except KeyError as e:
        print("Environment variable for database connection is missing: " + str(e))
        raise
    except Exception as e:
        print("Error getting DB environment variables: " + str(e))
        raise
    
    # Only pass optional parameters when they are set (not None or empty).
    kwargs = { 'db_server_and_port': db_server_and_port }
    if db_usr is not None and db_usr != "":
        kwargs['db_usr'] = db_usr
    if db_pwd is not None and db_pwd != "":
        kwargs['db_pwd'] = db_pwd
    if db_database is not None and db_database != "":
        kwargs['db_database'] = db_database

    return MongoDBClient(**kwargs)

# Create a module-level `db` instance so callers can import `db` directly
# Example: `from DB_client import db`
db = get_client()
