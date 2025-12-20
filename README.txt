There are 3 REST API endpoints that generate the json data you see in the data folder. What is your recomendation to create a database/repository with this data for millions of other users and matches.

REQUIRED environment variables:
riotapikey: key used when making API reqs to riot
sqlconnstr: database connection string. If it begins with "server" will default to sql server, if "mongo" will use mongoDB
sqlusr: user to login to database
sqlpwd: password to login to database


tables:
# summoner#, league_v4, match, match_participant


# only have 1 job for simplicity and to track # of requests
# it has to be repeatable and idempotent


start with own puuid in LeagueV4				
select from LeagueV4								## (sort highest games played? - likely to find new games). 	look at people not updated today


for puuid in puuids:
	get matches API for puuid
	remove matchIDs already in match table
			
	for match in matches:
		if matchId < NA1_5000000000 					## only recent games?
			continue
			
		# add matches to match table with null data??	nah, 
		# only commit once, for all match and participant data
		
		get match API
		
		# if match_json['info']['gameDuration'] < 200
		# if 420 (ranked) or 480 (swiftplay) queue type? (400 = unranked draft?)			## only include ranked / swiftplay in case the cols are different?
					
		## only commit once, for all match and participant data
		for participant in participants:
			if participant_puuid != puuid:									# don't update initial participant yet
				get league_v4 API
				for league in leagues:
					update league_v4 					## update everything EXCEPT [updateMatchesUtc]
				
		add match in match table (matchId, data version, gameCreation, gameDuration, gameEndTimestamp, gameId, gameMode, gameName, gameStartTimestamp, gameType, gameVersion, mapId, participants?)

	
## only update once all the puuid's matches have been inserted
get league_v4 API for puuid
update league_v4 										




NO COMPOSE FILE
	Build image
		docker build -t hello-python:latest .

		-t hello-python:latest tags the image with a name.
		. means the build context is the current folder.

	Run container
		docker run --rm hello-python:latest

		--rm removes the container after it exits.
		--name hello-python-latest  

WITH COMPOSE FILE
	build
		docker compose build app

	run	(-d: don't log to output)
		docker compose up -d app

	(to update docker env var have to restart vscode)
	build and run	(-d: don't log to output)
		docker compose up -d --build app

	down
		docker compose down -v

	tail logs	(last 100 lines)
		docker compose logs -f --tail 100 app

	push to docker.io
		docker compose push app

	build and push
		docker login && docker compose build app && docker compose push app