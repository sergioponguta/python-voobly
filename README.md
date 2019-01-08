[![PyPI version](https://badge.fury.io/py/voobly.svg)](https://badge.fury.io/py/voobly)

# python-voobly

Python 3 API for [Voobly](http://www.voobly.com), an online gaming platform. Makes requests to Voobly's public HTTP-based API.

## Prerequisites

- Active Voobly account
- API key provided by Voobly

## Install

`pip install voobly`

## Usage

See the [Voobly API documentation](http://www.voobly.com/pages/view/147/External-API-Documentation) for available parameters.

```python
import datetime
import voobly

# Establish a session. Use the API key provided by Voobly.
api_session = voobly.get_session(key="<your-api-key>", cache_expiry=datetime.timedelta(days=1))
# optionally, supply username and password (for match access only):
session = voobly.get_session(username="<your-voobly-username>", password="<your-voobly-password>")

# Validate API key
assert voobly.validate_key(api_session) == True

# Get lobby information for AoC
lobbies = voobly.get_lobbies(api_session, 13)                                  # returns list

# Look up a user ID based on username
uid = voobly.find_user(api_session, "TheViper")  # returns 123211439

# Look up user IDs for multiple usernames
results = voobly.find_users(api_session, "TheViper", "MBLAoC")  # returns list

# Get user profile for "TheViper"
profile = voobly.get_user(api_session, 123211439)
profile = voobly.get_user(api_session, "TheViper") # same result

# Get match information
match = voobly.get_match(session, 18786853)  # match id (last portion of URL), returns time played and rec links

# Download rec
filename = voobly.download_rec(session, "/files/view/50168753/9ogc...", "/save/to") # retrieve path from `get_match`

# Get top ten accounts on AoC "RM - 1v1" ladder
top_accounts = voobly.get_ladder(api_session, "RM - 1v1")
top_ten_accounts = top_accounts[0:10]


# Download last 9 games of each player player on a list, automatically create folder per player and format the rec names
for account in top_ten_accounts:

    games = voobly.get_last_matches(session, account['uid']) # returns list
    voobly.download_game_list(session, account['display_name'], games, '/save/') # downloads in C:/save/
    
# The following methods are helpers built from the previous.

# Get a user profile & ladder info based on username
user = voobly.user("TheViper", ladder_ids=[131, 132])  # returns dict, ladder_ids may be names

# Get a list of ladder IDs for AoC
ladders = voobly.ladders(session, 13)  # returns list
```

## Caveats

- `get_ladder` with a uid or uidlist does not return *global* ranking, only within results.


## Exception Handling

Exceptions raise a `VooblyError`, including connectivity issues, bad API key, and malformed results.

## Caching

To reduce load on the Voobly API, this module includes automatic HTTP request caching. The `cache_expiry` parameter of `get_session` determines how long requests are cached. This caching mechanism can be disabled if an external cache is implemented. Please use a maximum `cache_expiry` for your usecase. The default `cache_expiry` is 7 days.

## Development

### Lint

`tox`

### Release

`make release`

### Contributions

Contributions are welcome. Please submit a PR that passes `tox`.

## Disclaimer
Not affiliated with Voobly.
