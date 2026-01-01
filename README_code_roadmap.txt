
select from LeagueV4								## (sort highest games played? - likely to find new games). 	look at people not updated today
(if none, start with own puuid + games)

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
