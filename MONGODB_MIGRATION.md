# MongoDB Migration Guide

This repository has been migrated from Microsoft SQL Server to MongoDB.

## Environment Variables

The following environment variables are required to run the application:

### MongoDB Configuration (Required)
- `MONGO_URI`: MongoDB connection string (e.g., `mongodb://localhost:27017/` or `mongodb+srv://user:pass@cluster.mongodb.net/`)
- `MONGO_DB`: MongoDB database name (e.g., `lol_analysis`)

### Other Configuration
- Other existing environment variables for API access remain unchanged (e.g., API keys)

### Example .env file
```
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=lol_analysis
```

## MongoDB Collections

The application uses the following MongoDB collections:

1. **LeagueV4** - Stores League of Legends ranked player data
   - Key fields: `queueType`, `puuid`, `tier`, `rank`, `wins`, `losses`, etc.
   - Unique index: `{queueType: 1, puuid: 1}`

2. **Match** - Stores match data
   - Key fields: `matchId`, `dataVersion`, game info fields
   - Unique index: `{matchId: 1}`

3. **MatchParticipant** - Stores participant data for each match
   - Key fields: `matchId`, `puuid`, participant stats
   - Index: `{matchId: 1}`, `{puuid: 1}`

## Migration from SQL Server

If you have existing data in SQL Server that you want to migrate to MongoDB:

### Option 1: Export/Import JSON
1. Export data from SQL Server tables to JSON format
2. Import JSON data into MongoDB collections using `mongoimport` or Python scripts

### Option 2: Python Migration Script
Create a migration script that:
1. Connects to SQL Server and MongoDB simultaneously
2. Reads data from SQL Server tables
3. Transforms data as needed (e.g., add `totalGames` field calculated from `wins + losses`)
4. Inserts data into MongoDB collections

### Data Transformations
Note the following differences in data structure:

- **LeagueV4**: MongoDB version includes a `totalGames` field (calculated as `wins + losses`) used for sorting
- **Timestamps**: MongoDB uses `datetime` objects stored as BSON Date type, while SQL Server used `SYSUTCDATETIME()`
- **Field names**: MongoDB uses `matchId` (camelCase) while SQL Server used `matchID`

### Creating Indexes
For optimal performance, create indexes on frequently queried fields:

```python
from pymongo import ASCENDING, DESCENDING
db = mongo_conn.get_db()

# LeagueV4 indexes
db['LeagueV4'].create_index([('queueType', ASCENDING), ('puuid', ASCENDING)], unique=True)
db['LeagueV4'].create_index([('updateMatchesUtc', ASCENDING), ('totalGames', DESCENDING)])

# Match indexes
db['Match'].create_index([('matchId', ASCENDING)], unique=True)

# MatchParticipant indexes
db['MatchParticipant'].create_index([('matchId', ASCENDING)])
db['MatchParticipant'].create_index([('puuid', ASCENDING)])
```

## Running with Docker

Build the container:
```bash
docker build -t lol_analysis:latest .
```

Run with environment variables:
```bash
docker run --rm \
  -e MONGO_URI="mongodb://host.docker.internal:27017/" \
  -e MONGO_DB="lol_analysis" \
  lol_analysis:latest
```

Or use docker-compose with a `.env` file containing the MongoDB configuration.

## Changes from SQL Server

### Removed Dependencies
- `pyodbc` package
- `unixodbc-dev` system package
- `msodbcsql18` (Microsoft ODBC Driver 18)
- Microsoft package repositories

### Added Dependencies
- `pymongo` package

### Code Changes
- `sql_conn.py`: Deprecated (raises error if used)
- `mongo_conn.py`: New module for MongoDB connectivity
- `league_v4.py`: Updated to use MongoDB collections and upserts
- `match.py`: Updated to use MongoDB collections
- `match_participant.py`: Updated to use MongoDB collections
- `start.py`: Updated to use MongoDB bulk operations

### Transaction Handling
- SQL Server used connection/cursor with commit/rollback
- MongoDB uses bulk operations for batching multiple writes efficiently
- The `_no_commit` functions now accept a `bulk_operations` list parameter instead of a cursor
