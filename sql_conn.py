import pyodbc
from env_util import get_env_var

def get_db_connection(autocommit_b=True):
    """
    Establishes and returns a database connection.
    """
    try:
        sql_usr = get_env_var("sqlusr", required=True)
        sql_pwd = get_env_var("sqlpwd", required=True)
        sql_conn_str = get_env_var("sqlconnstr", required=True)

        conn_str = "Driver={ODBC Driver 18 for SQL Server};" + sql_conn_str + " \
            Uid=" + sql_usr + ";Pwd=" + sql_pwd + "; \
            Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

        # print(conn_str)
        # print(conn_str.format(sql_conn_str, sql_usr, sql_pwd))
        conn = pyodbc.connect(conn_str, autocommit=autocommit_b)
        return conn
    except pyodbc.Error as ex:
        sqlstate = ex.args[0] if ex.args else str(ex)
        print(f"Database connection error: {sqlstate}")
        raise
    except KeyError as e:
        print("Environment variable for database connection is missing: " + str(e))
        raise
    except Exception as e:
        print("Error connecting to database: " + str(e))
        raise

def close_db_connection(conn):
    """
    Closes the database connection.
    """
    if conn:
        conn.close()