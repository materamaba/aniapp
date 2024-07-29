from flask import Flask, redirect, request, url_for, make_response, render_template, jsonify
import os
import requests

app = Flask(__name__)

CLIENT_ID = os.getenv('CLIENT_ID', 'ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET', 'TOKEN')
REDIRECT_URI = 'https://materamaba.pythonanywhere.com/get'
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
