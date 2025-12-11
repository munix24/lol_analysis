from get_env_var import get_env_var
from DB_client_sql import SqlDBClient
from DB_client_mongo import MongoDBClient

def get_client():
    # Decide backend based on `sqlconnstr` content:
    # - If it starts with "Server", use SQL Server
    # - If it equals or starts with "mongo", use MongoDB
    # If `sqlconnstr` is missing or doesn't exist raise error
    sql_connstr = get_env_var('sqlconnstr', required=True)
    val = sql_connstr.strip()
    low = val.lower()
    if val.startswith('Server') or low.startswith('server'):
        return SqlDBClient()
    if low == 'mongo' or low.startswith('mongo'):
        return MongoDBClient()

# Create a module-level `db` instance so callers can import `db` directly
# Example: `from DB_client import db`
db = get_client()
