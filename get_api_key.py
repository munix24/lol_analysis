from env_util import get_env_var

def get_api_key():
    """Return Riot API key from environment.

    Supports Azure-style hyphen-lowercase names (e.g. `riot-api-key`) as well as
    `RIOT_API_KEY` via `env_util.get_env_var`.
    """
    return get_env_var("riotapikey", required=True)
