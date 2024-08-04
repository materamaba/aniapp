from flask import Flask, redirect, request, url_for, make_response, render_template, jsonify
import os
import requests
import time
import json

app = Flask(__name__)

CLIENT_ID = os.getenv('CLIENT_ID', '')
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '')
REDIRECT_URI = ''
ANILIST_AUTHORIZE_URL = 'https://anilist.co/api/v2/oauth/authorize'
ANILIST_TOKEN_URL = 'https://anilist.co/api/v2/oauth/token'

def get_access_token(code):
    data = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'code': code
    }
    response = requests.post(ANILIST_TOKEN_URL, data=data)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        return None

def get_username(token):
    query = '''
    query {
      Viewer {
        id
        name
      }
    }
    '''
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    response = requests.post('https://graphql.anilist.co', json={'query': query}, headers=headers)
    if response.status_code == 200:
        return response.json()['data']['Viewer']['name']
    else:
        return None

def get_anilist_avatar(username):
    query = '''
    query ($name: String) {
      User(name: $name) {
        avatar {
          medium
        }
      }
    }
    '''
    variables = {'name': username}
    response = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables})
    if response.status_code == 200:
        return response.json()['data']['User']['avatar']['medium']
    else:
        raise Exception(f"Failed to retrieve data: {response.status_code}, {response.text}")

def get_currently(typ, username, access_token):
    query = '''
    query ($userName: String, $typ: MediaType) {
        MediaListCollection(userName: $userName, type: $typ, status: CURRENT) {
            lists {
                entries {
                    media {
                        id
                        title {
                            romaji
                            english
                            native
                        }
                        episodes
                        coverImage {
                            large
                        }
                    }
                    progress
                }
            }
        }
    }
    '''
    variables = {'userName': username, 'typ': typ}
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    response = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables}, headers=headers)
    if response.status_code == 200:
        return response.json()['data']['MediaListCollection']['lists'][0]['entries']
    else:
        return []


def search_am(query, type, is_adult):
    ANIList_API_URL = "https://graphql.anilist.co"
    query_string = """
    query ($search: String, $type: MediaType, $isAdult: Boolean) {
        Page {
            media(search: $search, type: $type, isAdult: $isAdult) {
                id
                title {
                    romaji
                    english
                    native
                }
                coverImage {
                    large
                }
                isAdult
            }
        }
    }
    """
    variables = {"search": query, "type": type, "isAdult": is_adult}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    response = requests.post(ANIList_API_URL, json={'query': query_string, 'variables': variables}, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if 'errors' in data:
            print("Errors:", data['errors'])
        else:
            return data
    else:
        print(f"Request failed with status code {response.status_code}")






def info(id):
    query = """
    query ($id: Int, $asHtml: Boolean) {
      Media(id: $id) {
        id
        title {
          romaji
          english
          native
        }
        description(asHtml: $asHtml)
        startDate {
          year
          month
          day
        }
        endDate {
          year
          month
          day
        }
        season
        seasonYear
        type
        format
        status
        episodes
        duration
        chapters
        volumes
        genres
        tags {
          name
        }
        averageScore
        meanScore
        popularity
        source
        studios {
          edges {
            node {
              name
              isAnimationStudio
            }
          }
        }
        bannerImage
        coverImage {
          large
        }
      }
    }
    """
    variables = {"id": id, "asHtml": False}
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    try:
        response = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables}, headers=headers)
        response.raise_for_status()
        data = response.json()
        if 'errors' in data:
            print("GraphQL Errors:", data['errors'])
            return None
        return data.get('data', {}).get('Media', {})
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None




CACHE = {}
CACHE_EXPIRY_TIME = 86400  # Cache expiry time in seconds (1 day)

def cache_set(key, value):
    expiration = time.time() + CACHE_EXPIRY_TIME
    CACHE[key] = {'value': value, 'expires': expiration}

def cache_get(key):
    cached = CACHE.get(key)
    if cached and cached['expires'] > time.time():
        print("Cache hit!")
        return cached['value']
    print("Cache expired!")
    return None

def get_anime_themes(anilist_id):
    cached = cache_get(f'animethemes_{anilist_id}')
    if cached is not None:
        return cached

    include = "animethemes.animethemeentries.videos,animethemes.song,animethemes.song.artists"
    url = f"https://api.animethemes.moe/anime?filter[has]=resources&filter[site]=AniList&filter[external_id]={anilist_id}&include={include}"

    try:
        response = requests.get(url, headers={
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        response.raise_for_status()
        data = response.json()

        themes_info = {}
        anime_list = data.get('anime', [])
        if anime_list:
            anime = anime_list[0]
            animethemes = anime.get('animethemes', [])
            if animethemes:
                themes_info['themes'] = []
                for theme in animethemes:
                    song = theme.get('song', {})
                    song_title = song.get('title', 'Unknown Title')
                    artists = ', '.join(artist.get('name', 'Unknown Artist') for artist in song.get('artists', []))
                    theme_type = theme.get('type', 'Unknown Type')

                    entries = theme.get('animethemeentries', [])
                    video_url = 'No Video Link'
                    if entries and entries[0].get('videos'):
                        video_url = entries[0]['videos'][0].get('link', 'No Video Link')

                    themes_info['themes'].append({
                        'title': song_title,
                        'artist': artists,
                        'type': theme_type,
                        'video_url': video_url
                    })

                cache_set(f'animethemes_{anilist_id}', themes_info)
                return themes_info

    except requests.RequestException as e:
        print(f"An error occurred: {e}")
        return None


@app.route('/about')
def media_page():
    media_id = request.args.get('id', type=int)
    if media_id is None:
        return "Media ID is required", 400
    data = info(media_id)
    if data is None:
        return "Failed to retrieve media information.", 500
    return render_template('about.html', media=data)



@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    is_adult = request.args.get('isAdult') == 'on'
    anime = []
    manga = []

    # Ustawienie filtra
    is_adult_filter = True if is_adult else False

    if query:
        data = search_am(query, "ANIME", is_adult_filter)
        if data:
            anime = data.get('data', {}).get('Page', {}).get('media', [])
        data = search_am(query, "MANGA", is_adult_filter)
        if data:
            manga = data.get('data', {}).get('Page', {}).get('media', [])
    return render_template('search.html', query=query, anime=anime, manga=manga, isAdult=is_adult)







@app.route('/update_episode', methods=['GET'])
def update_episode():
    username = request.cookies.get('username')
    access_token = request.cookies.get('access_token')
    media_id = request.args.get('id')
    media_type = request.args.get('type', 'ANIME').upper()

    if username and access_token and media_id:
        query = '''
        query ($username: String, $type: MediaType) {
          MediaListCollection(userName: $username, type: $type, status: CURRENT) {
            lists {
              entries {
                media {
                  id
                }
                progress
              }
            }
          }
        }
        '''
        variables = {'username': username, 'type': media_type}
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        response = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables}, headers=headers)
        if response.status_code == 200:
            anime_list = response.json()['data']['MediaListCollection']['lists'][0]['entries']
            progress = next(item['progress'] for item in anime_list if item['media']['id'] == int(media_id))

            mutation = '''
            mutation ($mediaId: Int!, $progress: Int!) {
              SaveMediaListEntry (mediaId: $mediaId, progress: $progress) {
                media {
                  id
                }
                progress
              }
            }
            '''
            new_progress = progress + 1
            variables = {'mediaId': int(media_id), 'progress': new_progress}
            response = requests.post('https://graphql.anilist.co', json={'query': mutation, 'variables': variables}, headers=headers)
            if response.status_code == 200:
                return redirect(url_for('home'))
            else:
                return jsonify({'success': False, 'error': response.text}), 500
        else:
            return jsonify({'success': False, 'error': response.text}), 500
    else:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

@app.route('/')
def home():
    username = request.cookies.get('username')
    access_token = request.cookies.get('access_token')
    if username and access_token:
        avatar = get_anilist_avatar(username)
        anime = get_currently("ANIME", username, access_token)
        manga = get_currently("MANGA", username, access_token)
        return render_template('home.html', username=username, avatar=avatar, anime=anime, manga=manga)
    else:
        return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/get')
def get_token():
    code = request.args.get('code')
    if code:
        token = get_access_token(code)
        if token:
            username = get_username(token)
            if username:
                response = make_response(redirect(url_for('home')))
                response.set_cookie('username', username, samesite='Lax')
                response.set_cookie('access_token', token, samesite='Lax')
                return response
            else:
                return "Failed to retrieve username", 500
        else:
            return "Failed to retrieve access token", 500
    else:
        return "No code provided", 400

if __name__ == "__main__":
    app.run(debug=True)
