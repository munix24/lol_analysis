"""
DEPRECATED: This module is deprecated and should not be used.
The application has migrated from SQL Server to MongoDB.
Use mongo_conn.py instead.
"""

def get_db_connection(autocommit_b=True):
    """
    DEPRECATED: Use mongo_conn.get_db() instead.
    """
    raise RuntimeError(
        "sql_conn.get_db_connection() is deprecated. "
        "The application has migrated to MongoDB. "
        "Use mongo_conn.get_db() instead."
    )

def close_db_connection(conn):
    """
    DEPRECATED: Use mongo_conn.close_db_connection() instead.
    """
    raise RuntimeError(
        "sql_conn.close_db_connection() is deprecated. "
        "The application has migrated to MongoDB. "
        "Use mongo_conn.close_db_connection() instead."
    )