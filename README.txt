There are 3 REST API endpoints that generate the json data you see in the data folder. What is your recomendation to create a database/repository with this data for millions of other users and matches.

REQUIRED environment variables:
riotapikey: key used when making API reqs to riot

OPTIONAL environment variables: (if not provided will connect to local network mongoDB)
dbserverandport: database connection string. If it begins with "server" will default to sql server, if "mongo" will use mongoDB
dbusr: user to login to database
dbpwd: password to login to database
dbdatabase: database name


tables:
# summoner#, league_v4, match, match_participant


# only have 1 job for simplicity and to track # of requests
# it has to be repeatable and idempotent


start with own puuid in LeagueV4	


-- can log in without user / pwd 
localhost mongodb
	docker run --name mongodb -p 27017:27017 -d mongodb/mongodb-community-server:latest

-- -v attach volume?
localhost mongodb with user / pwd + volume
	docker run --name mongodb -p 27017:27017 -d /
		-e MONGO_INITDB_ROOT_USERNAME=mongoadmin / 
		-e MONGO_INITDB_ROOT_PASSWORD=secret / 
		-v volume?
		mongodb/mongodb-community-server:latest


docker service update --env-add riotapikey="RGAPI-08cc3e12-9798-49f9-933c-b3c4178adf73" lol_analysis_app

docker run -d --restart=on-failure:3 --name lol_analysis_app -e riotapikey="%apikey%" munix244/lol_analysis_app
docker run -d --restart=on-failure:3 --name lol_analysis_app --env-file ./lol_analysis/env_mongo_db.env munix244/lol_analysis_app

