-- Created by GitHub Copilot in SSMS - review carefully before executing
CREATE TABLE LeagueV4 (
    puuid         VARCHAR(100)     NOT NULL,
    queueType     VARCHAR(30)      NOT NULL,
    tier          VARCHAR(20)      NOT NULL,
    rank          VARCHAR(5)       NOT NULL,
    leaguePoints  INT              NOT NULL,
	totalGames  AS ([wins]+[losses]),
    wins          INT              NOT NULL,
    losses        INT              NOT NULL,
    veteran       BIT              NOT NULL,
    inactive      BIT              NOT NULL,
    freshBlood    BIT              NOT NULL,
    hotStreak     BIT              NOT NULL,
    leagueId      UNIQUEIDENTIFIER NOT NULL,
	createUtc datetime2(7) NOT NULL CONSTRAINT [DF_LeagueV4_createUtc] DEFAULT (SYSUTCDATETIME()),
	updateRankUtc datetime2(7) NOT NULL CONSTRAINT [DF_LeagueV4_updateRankUtc] DEFAULT (SYSUTCDATETIME()),
	updateMatchesUtc datetime2(7) NOT NULL CONSTRAINT [DF_LeagueV4_updateMatchesUtc] DEFAULT (SYSUTCDATETIME()),

    CONSTRAINT PK_LeagueV4 PRIMARY KEY (puuid, queueType)
);