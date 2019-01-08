"""Voobly API.

Documentation: http://www.voobly.com/pages/view/147/External-API-Documentation

A Voobly user account is required.
An API key granted by Voobly is also requred.

Please note that every attempt has been made to avoid scraping, to include:
    - caching reference metadata
    - caching requests
    - limiting scraping to essential functionality
    - fully supporting external API
"""

import datetime
import io
import json
import logging
import os
import pkg_resources
import pickle
import re
import zipfile

import bs4
import dateparser
import requests
import requests_cache
import tablib
from requests.auth import AuthBase
from requests.exceptions import RequestException
from tablib.core import UnsupportedFormat


_LOGGER = logging.getLogger(__name__)
COOKIE_PATH = './voobly_cookies.pickle'
BASE_URL = 'https://www.voobly.com'
VOOBLY_API_URL = BASE_URL + '/api/'
LOGIN_PAGE = BASE_URL + '/login'
LOGIN_URL = BASE_URL + '/login/auth'
MATCH_URL = BASE_URL + '/match/view'
RECORDING_MATCHES_URL = BASE_URL + '/recording/browse'
PROFILE_PATH = '/profile/view'
FIND_USER_URL = 'finduser/'
FIND_USERS_URL = 'findusers/'
LOBBY_URL = 'lobbies/'
LADDER_URL = 'ladder/'
USER_URL = 'user/'
VALIDATE_URL = 'validate'
LADDER_RESULT_LIMIT = 40
METADATA_PATH = 'metadata'
SCRAPE_FETCH_ERROR = 'Page Access Failed'
SCRAPE_PAGE_NOT_FOUND = 'Page Not Found'
MATCH_NEW_RATE = 'New Rating:'
MATCH_DATE_PLAYED = 'Date Played:'
COLOR_MAPPING = {
    '#0054A6': 0,
    '#FF0000': 1,
    '#00A651': 2,
    '#FFFF00': 3,
    '#00FFFF': 4,
    '#92278F': 5,
    '#C0C0C0': 6,
    '#FF8000': 7
}

CIV_IMAGE_ID = {
    '1.' : 'Brit',
    '2.' : 'Frank',
    '3.' : 'Goth',
    '4.' : 'Teu',
    '5.' : 'Jap',
    '6.' : 'Chi',
    '7.' : 'Byz',
    '8.' : 'Per',
    '9.' : 'Sar',
    '10' : 'Turk',
    '11' : 'Vik',
    '12' : 'Mon',
    '13' : 'Cel',
    '14' : 'Spa',
    '15' : 'Azt',
    '16' : 'May',
    '17' : 'Hun',
    '18' : 'Kor',
    '19' : 'Ita',
    '20' : 'Ind',
    '21' : 'Inc',
    '22' : 'Mag',
    '23' : 'Sla',
    '24' : 'Por',
    '25' : 'Eth',
    '26' : 'Mal',
    '27' : 'Ber',
    '28' : 'Khm',
    '29' : 'Malay',
    '30' : 'Bur',
    '31' : 'Vie'
}


def get_metadata_path(name):
    """Get reference metadata file path."""
    return pkg_resources.resource_filename('voobly', os.path.join(METADATA_PATH, '{}.json'.format(name)))


GAMES = json.loads(open(get_metadata_path('games')).read())
LADDERS = json.loads(open(get_metadata_path('ladders')).read())


class VooblyError(Exception):
    """Voobly error."""

    pass


def _save_cookies(requests_cookiejar, filename):
    """Save cookies to a file."""
    with open(filename, 'wb') as handle:
        pickle.dump(requests_cookiejar, handle)


def _load_cookies(filename):
    """Load cookies from a file."""
    with open(filename, 'rb') as handle:
        return pickle.load(handle)


def _make_request(session, url, argument=None, params=None, raw=False):
    """Make a request to API endpoint."""
    if not params:
        params = {}
    params['key'] = session.auth.key
    try:
        if argument:
            request_url = '{}{}{}'.format(VOOBLY_API_URL, url, argument)
        else:
            request_url = '{}{}'.format(VOOBLY_API_URL, url)
        resp = session.get(request_url, params=params)
    except RequestException:
        raise VooblyError('connection problem')
    if resp.text == 'bad-key':
        raise VooblyError('bad api key')
    elif resp.text == 'too-busy':
        raise VooblyError('service too busy')
    elif not resp.text:
        raise VooblyError('no data returned')
    if raw:
        return resp.text
    try:
        return tablib.Dataset().load(resp.text).dict
    except UnsupportedFormat:
        raise VooblyError('unexpected error {}'.format(resp.text))


def make_scrape_request(session, url):
    """Make a request to URL."""
    html = session.get(url)
    if SCRAPE_FETCH_ERROR in html.text:
        raise VooblyError('not logged in')
    if html.status_code != 200 or SCRAPE_PAGE_NOT_FOUND in html.text:
        raise VooblyError('page not found')
    return bs4.BeautifulSoup(html.text, features='html.parser')


def lookup_ladder_id(name):
    """Lookup ladder id based on name."""
    if name not in LADDERS:
        raise VooblyError('could not find ladder id for "{}"'.format(name))
    return LADDERS[name]['id']


def lookup_game_id(name):
    """Lookup game id based on name."""
    if name not in GAMES:
        raise VooblyError('could not find game id for "{}"'.format(name))
    return GAMES[name]['id']


# pylint: disable=too-many-arguments
def get_ladder(session, ladder_id, user_id=None, user_ids=None, start=0, limit=LADDER_RESULT_LIMIT):
    """Get ladder."""
    params = {
        'start': start,
        'limit': limit
    }
    if isinstance(ladder_id, str):
        ladder_id = lookup_ladder_id(ladder_id)
    if limit > LADDER_RESULT_LIMIT:
        raise VooblyError('limited to 40 rows')
    if user_ids:
        params['uidlist'] = ','.join([str(uid) for uid in user_ids])
    elif user_id:
        params['uid'] = user_id
    resp = _make_request(session, LADDER_URL, ladder_id, params)
    if user_id:
        if not resp:
            raise VooblyError('user not ranked')
        return resp[0]
    return resp


def get_lobbies(session, game_id):
    """Get lobbies for a game."""
    if isinstance(game_id, str):
        game_id = lookup_game_id(game_id)
    lobbies = _make_request(session, LOBBY_URL, game_id)
    for lobby in lobbies:
        # pylint: disable=len-as-condition
        if len(lobby['ladders']) > 0:
            lobby['ladders'] = lobby['ladders'][:-1].split('|')
    return lobbies


def get_user(session, user_id):
    """Get user."""
    if isinstance(user_id, str):
        user_id = find_user(session, user_id)
    resp = _make_request(session, USER_URL, user_id)
    if not resp:
        raise VooblyError('user id not found')
    return resp[0]


def find_user(session, username):
    """Find user by name - returns user ID."""
    resp = _make_request(session, FIND_USER_URL, username)
    if not resp:
        raise VooblyError('user not found')
    try:
        return int(resp[0]['uid'])
    except ValueError:
        raise VooblyError('user not found')


def find_users(session, *usernames):
    """Find multiple users by name."""
    user_string = ','.join(usernames)
    return _make_request(session, FIND_USERS_URL, user_string)


def validate_key(session):
    """Validate API key."""
    resp = _make_request(session, VALIDATE_URL, raw=True)
    return resp == 'valid-key'


def user(session, username, ladder_ids=None):
    """Get all possible user info by name."""
    uid = find_user(session, username)
    data = get_user(session, uid)
    resp = dict(data)
    if not ladder_ids:
        return resp
    resp['ladders'] = {}
    for ladder_id in ladder_ids:
        if isinstance(ladder_id, str):
            ladder_id = lookup_ladder_id(ladder_id)
        try:
            ladder_data = dict(get_ladder(session, ladder_id, user_id=uid))
            resp['ladders'][ladder_id] = ladder_data
        except VooblyError:
            # No ranking on ladder
            pass
    return resp


def ladders(session, game_id):
    """Get a list of ladder IDs."""
    if isinstance(game_id, str):
        game_id = lookup_game_id(game_id)
    lobbies = get_lobbies(session, game_id)
    ladder_ids = set()
    for lobby in lobbies:
        ladder_ids |= set(lobby['ladders'])
    return list(ladder_ids)


def authenticated(function):
    """Re-authenticate if session expired."""
    def wrapped(session, *args):
        """Wrap function."""
        with session.cache_disabled():
            try:
                return function(session, *args)
            except VooblyError:
                _LOGGER.info("attempted to access page before login")
                login(session)
                return function(session, *args)
    return wrapped


@authenticated
def get_last_matches(session, user_id):
    """get 9 last games from a player."""
    url = '{}/{}'.format(RECORDING_MATCHES_URL, user_id)
    parsed = make_scrape_request(session, url)
    parsed_text = str(parsed)
    game_list = []
    end_index = 0

    for i in range(0, 9):
        start_index = parsed_text.find("Match:", end_index)
        match_index = parsed_text.find("#", start_index) + 1
        end_index = parsed_text.find("<", match_index)
        game_list.append(get_match(session, parsed_text[match_index:end_index]))
        #print(game_list[i]['players'][0]['url'])

    return game_list

@authenticated
def download_game_list(session, username, game_list, target_path):

    """Download, extract and sort by player and civ a list of recorded games."""

    for i in game_list:
        resp = session.get(BASE_URL + i['players'][0]['url'])

        
        if len(i) == 2: #Only for 1v1 games

            downloaded = zipfile.ZipFile(io.BytesIO(resp.content))
            downloaded.extractall(target_path + username + "/")
            date =  downloaded.namelist()[0][4:-4]
            
            old_file = os.path.join(target_path + username + "/", downloaded.namelist()[0])
            new_file = os.path.join(target_path + username + "/", "[" + date + "]" + i['players'][0]['username'] + "(" + i['players'][0]['civ'] + ")" + " vs " + i['players'][1]['username'] + "(" + i['players'][1]['civ'] + ")")
            try:
                os.rename(old_file, new_file)
            except FileExistsError:
                
                os.remove(old_file)

    return downloaded.namelist()

@authenticated
def get_match(session, match_id):
    """Get match metadata."""
    url = '{}/{}'.format(MATCH_URL, match_id)
    parsed = make_scrape_request(session, url)
    parsed_string = str(parsed)
    date_played = parsed.find(text=MATCH_DATE_PLAYED).find_next('td').text
    civs_index = [m.start() for m in re.finditer('res/games/AOC/civs/', parsed_string)]
    player_url_index = [m.start() for m in re.finditer('https://voobly.com/profile/view/', parsed_string)]
    players_aux = []
    players_ids = []
    civs_names = []
    players = []
    colors = {}
    civs = {}


    for i in range(1, (len(civs_index) * 2), 2):
        players_aux.append(player_url_index[i])


    for i in players_aux:

        index = parsed_string.find('"', i + 32)
        players_ids.append(parsed_string[i + 32:index])
    

    for i in civs_index:
        civs_names.append(CIV_IMAGE_ID[parsed_string[i + 19:i + 21]])
        
    for i in range(len(civs_names)):
        civs[players_ids[i]] = civs_names[i]

    for div in parsed.findAll('div', style=True):
        if div['style'].startswith('background-color:'):
            name = div.find_next('a', href=re.compile(PROFILE_PATH)).text
            color = div['style'].split(':')[1].split(';')[0].strip()
            colors[name] = color


    for i, rec in enumerate(parsed.find_all('a', href=re.compile('^/files/view'))):
        player_name = rec.find('b').text
        username = player_name.split(']')[-1]
        clan = player_name.split(']')[0][1:] if player_name.find(']') > 0 else None
        user = parsed.find('a', text=username)
        if not user:
            # bugged match page
            continue
        user_id = int(user['href'].split('/')[-1])
        children = list(user.find_next('span').children)
        rate_after = None
        rate_before = None
        if str(children[0]).strip() == MATCH_NEW_RATE:
            rate_after = int(children[1].text)
            rate_before = rate_after - int(children[3].text)
        elif str(children[4]).strip() == MATCH_NEW_RATE:
            rate_after = int(children[5].text)
            rate_before = rate_after - int(children[3].text)
        players.append({
            'url': rec['href'],
            'id': user_id,
            'username': username,
            'clan': clan,
            'civ': civs[str(user_id)],
            'color_id': COLOR_MAPPING.get(colors[username]),
            'rate_before': rate_before,
            'rate_after': rate_after
        })
    return {
        'timestamp': dateparser.parse(date_played),
        'players': players
    }


@authenticated
def download_rec(session, rec_url, target_path):
    """Download and extract a recorded game."""
    resp = session.get(BASE_URL + rec_url)
    downloaded = zipfile.ZipFile(io.BytesIO(resp.content))
    downloaded.extractall(target_path)
    return downloaded.namelist()[0] # never more than one rec


def login(session):
    """Login to Voobly."""
    if not session.auth.username or not session.auth.password:
        raise VooblyError('must supply username and password')
    _LOGGER.info("logging in (no valid cookie found)")
    session.cookies.clear()
    session.get(LOGIN_PAGE)
    resp = session.post(LOGIN_URL, data={
        'username': session.auth.username,
        'password': session.auth.password
    })
    if resp.status_code != 200:
        raise VooblyError('failed to login')
    _save_cookies(session.cookies, session.auth.cookie_path)


def get_session(key=None, username=None, password=None, cache=True,
                cache_expiry=datetime.timedelta(days=7), cookie_path=COOKIE_PATH):
    """Get Voobly API session."""
    class VooblyAuth(AuthBase):  # pylint: disable=too-few-public-methods
        """Voobly authorization storage."""

        def __init__(self, key, username, password, cookie_path):
            """Init."""
            self.key = key
            self.username = username
            self.password = password
            self.cookie_path = cookie_path

        def __call__(self, r):
            """Call is no-op."""
            return r

    session = requests.session()
    if cache:
        session = requests_cache.core.CachedSession(expire_after=cache_expiry)
    session.auth = VooblyAuth(key, username, password, cookie_path)
    if os.path.exists(cookie_path):
        _LOGGER.info("cookie found at: %s", cookie_path)
        session.cookies = _load_cookies(cookie_path)
    return session
