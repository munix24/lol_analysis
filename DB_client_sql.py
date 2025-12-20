import pyodbc
import pandas as pd
from get_env_var import get_env_var
from typing import Any, Dict, List, Tuple


class SqlDBClient:
	def __init__(self, db_usr: str = None, db_pwd: str = None, db_server_and_port: str = None, db_database: str = None):
		# Allow passing credentials/connstr in from caller; fall back to env vars
		self.db_usr = db_usr
		self.db_pwd = db_pwd
		self.db_server_and_port = db_server_and_port
		self.db_database = db_database

	def get_db_connection(self, autocommit_b=True):
		"""
		Establishes and returns a database connection.
		"""
		conn_str = "Driver={ODBC Driver 18 for SQL Server}; \
			Server=tcp:" + self.db_server_and_port + "; \
			Database=" + self.db_database + "; \
			Uid=" + self.db_usr + "; \
			Pwd=" + self.db_pwd + "; \
			Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

		try:
			conn = pyodbc.connect(conn_str, autocommit=autocommit_b)
			return conn
		except pyodbc.Error as ex:
			sqlstate = ex.args[0] if ex.args else str(ex)
			print(f"Database connection error: {sqlstate}")
			raise
		except Exception as e:
			print("Error connecting to database: " + str(e))
			raise

	def close_db_connection(self, conn):
		"""
		Closes the database connection.
		"""
		if conn:
			conn.close()
			
	def begin_transaction(self) -> Tuple[Any, Any]:
		conn = self.get_db_connection(False)
		return conn, conn.cursor()

	def commit_transaction(self, txn: Tuple[Any, Any]):
		conn, cursor = txn
		conn.commit()

	def close_transaction(self, txn: Tuple[Any, Any]):
		conn, cursor = txn
		try:
			cursor.close()
		except Exception:
			pass
		self.close_db_connection(conn)

	def select_oldest_ranked_puuids_df(self) -> pd.DataFrame:
		conn = self.get_db_connection()
		sql_query = "SELECT puuid FROM dbo.LeagueV4 \
			where queueType = 'RANKED_SOLO_5x5' \
			order by updateMatchesUtc asc, totalGames desc"
		df = pd.read_sql(sql_query, conn)
		self.close_db_connection(conn)
		return df

	def select_matches_in_list_not_in_table(self, matchIDs_list: List[str]) -> List[str]:
		if not matchIDs_list:
			return []

		conn = self.get_db_connection()
		cursor = conn.cursor()

		placeholders = ','.join('?' for _ in matchIDs_list)
		query = f"SELECT matchId FROM dbo.Match WHERE matchId IN ({placeholders})"
		cursor.execute(query, matchIDs_list)
		matchIDs_existing = {row[0] for row in cursor.fetchall()}
		self.close_db_connection(conn)

		return [m for m in matchIDs_list if m not in matchIDs_existing]

	def insert_match_no_commit(self, matchID: str, dataVersion: str, match_info_json: Dict[str, Any], txn: Tuple[Any, Any]):
		conn, cursor = txn
		exclude_keys = {"participants", "teams"}
		exclude_keys.add("gameModeMutators")
		columns = [k for k in match_info_json.keys() if k not in exclude_keys]
		column_names = ", ".join(columns)
		placeholders = ", ".join(["?"] * (len(columns) + 2))
		sql = f"INSERT INTO Match (matchID, dataVersion, {column_names}) VALUES ({placeholders})"
		values = [match_info_json[col] for col in columns]
		values.insert(0, matchID)
		values.insert(1, dataVersion)
		cursor.execute(sql, values)

	def insert_participants_no_commit(self, matchID: str, participant_json: List[Dict[str, Any]], txn: Tuple[Any, Any]):
		conn, cursor = txn
		exclude_keys = {"perks", "challenges", "missions"}
		exclude_keys.add("bountyLevel")
		columns = [k for k in participant_json[0].keys() if k not in exclude_keys]
		column_names = ", ".join(columns)
		placeholders = ", ".join(["?"] * (len(columns) + 1))
		sql = f"INSERT INTO MatchParticipant (matchID, {column_names}) VALUES ({placeholders})"

		for participant in participant_json:
			values = [participant[col] for col in columns]
			values.insert(0, matchID)
			cursor.execute(sql, values)

	def merge_league_v4_no_commit(self, leagues_v4_json: Dict[str, Any], txn: Tuple[Any, Any]):
		"""Execute the MERGE for a single league_v4 JSON using provided (conn, cursor) txn without committing."""
		conn, cursor = txn
		sql = """
		MERGE dbo.LeagueV4 AS target
		USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS src (
			leagueId, queueType, tier, rank, puuid,
			leaguePoints, wins, losses,
			veteran, inactive, freshBlood, hotStreak
		)
		ON  target.queueType = src.queueType
		AND target.puuid = src.puuid

		WHEN MATCHED THEN UPDATE SET
			target.leagueId = src.leagueId,
			target.tier = src.tier,
			target.rank = src.rank,
			target.leaguePoints = src.leaguePoints,
			target.wins = src.wins,
			target.losses = src.losses,
			target.veteran = src.veteran,
			target.inactive = src.inactive,
			target.freshBlood = src.freshBlood,
			target.hotStreak = src.hotStreak,
			target.updateRankUtc = SYSUTCDATETIME()

		WHEN NOT MATCHED THEN INSERT (
			leagueId, queueType, tier, rank, puuid,
			leaguePoints, wins, losses,
			veteran, inactive, freshBlood, hotStreak
		)
		VALUES (
			src.leagueId, src.queueType, src.tier, src.rank, src.puuid,
			src.leaguePoints, src.wins, src.losses,
			src.veteran, src.inactive, src.freshBlood, src.hotStreak
		);
		"""
		for league_v4_json in leagues_v4_json:
			cursor.execute(sql, (
				league_v4_json["leagueId"],
				league_v4_json["queueType"],
				league_v4_json["tier"],
				league_v4_json["rank"],
				league_v4_json["puuid"],
				league_v4_json["leaguePoints"],
				league_v4_json["wins"],
				league_v4_json["losses"],
				league_v4_json["veteran"],
				league_v4_json["inactive"],
				league_v4_json["freshBlood"],
				league_v4_json["hotStreak"]
		))

	def merge_league_v4(self, puuid, leagues_v4_json: List[Dict[str, Any]]):
		conn = self.get_db_connection(False)
		cursor = conn.cursor()

		for league_v4_json in leagues_v4_json:
			# use internal no-commit helper
			self.merge_league_v4_no_commit(league_v4_json, (conn, cursor))
			# update the last-matches timestamp for this puuid as part of the same txn

		# call the timestamp updater once per call (keeps original logic)
		self.update_matches_utc_no_commit(puuid, (conn, cursor))

		conn.commit()
		cursor.close()
		self.close_db_connection(conn)

	def update_matches_utc_no_commit(self, puuid: str, txn: Tuple[Any, Any]):
		"""Update the [updateMatchesUtc] timestamp for the given puuid using the provided (conn, cursor) txn."""
		conn, cursor = txn
		if not puuid:
			return
		sql = "UPDATE dbo.LeagueV4 SET [updateMatchesUtc] = SYSUTCDATETIME() WHERE puuid = ?"
		cursor.execute(sql, (puuid,))
