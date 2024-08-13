from flask import Flask, redirect, request, url_for, make_response, render_template, jsonify
import os
import requests
from datetime import datetime

app = Flask(__name__)

CLIENT_ID = os.getenv('CLIENT_ID', '')
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '')
REDIRECT_URI = ''
ANILIST_AUTHORIZE_URL = 'https://anilist.co/api/v2/oauth/authorize'
ANILIST_TOKEN_URL = 'https://anilist.co/api/v2/oauth/token'
ANILIST_API_URL = "https://graphql.anilist.co"


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
        avatar {
          large
        }
        unreadNotificationCount
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
        data = response.json()
        print("User data:", data)  # Debugging output
        viewer = data.get('data', {}).get('Viewer', {})
        return {
            'id': viewer.get('id'),
            'name': viewer.get('name'),
            'avatar': viewer.get('avatar', {}).get('large'),
            'unreadNotificationCount': viewer.get('unreadNotificationCount')
        }
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None


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
        data = response.json().get('data', {}).get('MediaListCollection', {}).get('lists', [])
        if data and len(data) > 0:
            return data[0].get('entries', [])
        return []
    else:
        return []


@app.route('/')
def home():
    username = request.cookies.get('username')
    access_token = request.cookies.get('access_token')
    if username and access_token:
        user_data = get_username(access_token)
        if not user_data:
            return redirect(url_for('login'))

        anime = get_currently("ANIME", username, access_token)
        manga = get_currently("MANGA", username, access_token)
        return render_template(
            'home.html',
            username=user_data['name'],
            avatar=user_data['avatar'],
            unread_notification_count=user_data['unreadNotificationCount'],
            anime=anime,
            manga=manga
        )
    else:
        return redirect(url_for('login'))


@app.route('/login')
def login():
    return render_template('login.html')



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
    	  relations {
    	    edges {
            relationType
            node{
              id
              title{
                romaji
              }
              coverImage {
                medium
              }
            }
    	    }
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
    variables = {"id": id, "asHtml": True}
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


def get_user_anime_status(media_id):
    query = '''
    query ($username: String, $mediaId: Int) {
        MediaList (userName: $username, mediaId: $mediaId) {
            status
        }
    }
    '''
    variables = {"username": request.cookies.get('username'), "mediaId": media_id}

    access_token = request.cookies.get('access_token')

    if not access_token:
        return {"error": "Access token is missing"}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables}, headers=headers)
        response.raise_for_status()
        data = response.json()

        if 'errors' in data:
            for error in data['errors']:
                if error.get('status') == 404:
                    return {"status": "add_to_list"}
            return {"error": data['errors']}

        status = data['data']['MediaList']['status']
        return {"status": status}

    except requests.exceptions.RequestException as e:
        if "404" in str(e):
            return {"status": "add_to_list"}
        return {"error": str(e)}


@app.route('/about')
def media_page():
    username = request.cookies.get('username')
    access_token = request.cookies.get('access_token')
    if not username or not access_token:
        return redirect(url_for('login'))
    media_id = request.args.get('id', type=int)
    if media_id is None:
        return "Media ID is required", 400
    status = get_user_anime_status(media_id)
    data = info(media_id)
    if data is None:
        return "Failed to retrieve media information.", 500

    return render_template('about.html', media=data, status=status)


@app.route('/update_status', methods=['POST'])
def update_status():
    data = request.get_json()
    status = data.get('status')
    media_id = data.get('media_id')

    access_token = request.cookies.get('access_token')
    if not access_token:
        return jsonify({"success": False, "error": "Access token is missing"}), 400

    mutation = '''
    mutation ($mediaId: Int, $status: MediaListStatus) {
        SaveMediaListEntry (mediaId: $mediaId, status: $status) {
            status
        }
    }
    '''
    variables = {
        "mediaId": media_id,
        "status": status.upper()
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post('https://graphql.anilist.co', json={'query': mutation, 'variables': variables}, headers=headers)
        response.raise_for_status()
        data = response.json()

        if 'errors' in data:
            return jsonify({"success": False, "error": data['errors']}), 400

        return jsonify({"success": True}), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": str(e)}), 500



@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    is_adult = request.args.get('isAdult') == 'on'
    anime = []
    manga = []

    is_adult_filter = True if is_adult else False

    if query:
        data = search_am(query, "ANIME", is_adult_filter)
        if data:
            anime = data.get('data', {}).get('Page', {}).get('media', [])
        data = search_am(query, "MANGA", is_adult_filter)
        if data:
            manga = data.get('data', {}).get('Page', {}).get('media', [])
    return render_template('search.html', query=query, anime=anime, manga=manga, isAdult=is_adult)



def get_current_season():
    month = datetime.now().month
    if 1 <= month <= 3:
        return "WINTER"
    elif 4 <= month <= 6:
        return "SPRING"
    elif 7 <= month <= 9:
        return "SUMMER"
    else:
        return "FALL"

def brws(s, y, p):
    ANIList_API_URL = "https://graphql.anilist.co"
    query = '''
    query ($season: MediaSeason, $seasonYear: Int, $page: Int) {
        Page(page: $page, perPage: 20) {
            media(season: $season, seasonYear: $seasonYear) {
                id
                title {
                    romaji
                }
                coverImage {
                    large
                }
                isAdult
            }
            pageInfo {
                currentPage
                hasNextPage
            }
        }
    }
    '''

    variables = {
        "page": p,
        "season": s,
        "seasonYear": y
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    response = requests.post(ANIList_API_URL, json={'query': query, 'variables': variables}, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")

@app.route('/browse')
def browse():
    default_season = get_current_season()
    default_year = datetime.now().year
    default_page = 1

    season = request.args.get('s', default_season)
    year = request.args.get('y', default_year)
    page = request.args.get('p', default_page)

    try:
        year = int(year)
        page = int(page)
    except ValueError:
        return "Invalid year or page number", 400

    content = brws(season, year, page)
    return render_template('browse.html', b=content, current_season=season, current_year=year, current_page=page)


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


@app.route('/get')
def get_token():
    code = request.args.get('code')
    if not code:
        return "No code provided", 400

    try:
        token = get_access_token(code)
        if not token:
            return "Failed to retrieve access token", 500

        username = get_username(token)
        if not username:
            return "Failed to retrieve username", 500

        response = make_response(redirect(url_for('home')))
        response.set_cookie('username', username['name'], samesite='Lax')
        response.set_cookie('access_token', token, samesite='Lax')
        return response

    except Exception as e:
        print(f"Error during /get processing: {e}")
        return "Internal Server Error", 500


def fetch_activity(access_token, following=True, page=1, per_page=20):
    query = '''
    query ($page: Int, $perPage: Int, $isFollowing: Boolean, $sort: [ActivitySort]) {
      Page(page: $page, perPage: $perPage) {
        activities(isFollowing: $isFollowing, sort: $sort) {
          ... on ListActivity {
            id
            user {
              name
              avatar {
                medium
              }
            }
            media {
              id
              title {
                romaji
              }
              coverImage {
                medium
              }
            }
            status
            progress
            isLiked
            likeCount
            createdAt
          }
        }
      }
    }
    '''
    variables = {
        'page': page,
        'perPage': per_page,
        'isFollowing': following,
        'sort': ["ID_DESC"]
    }

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    try:
        response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables}, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching activities: {e}")
        return []

    data = response.json()

    activities = data.get('data', {}).get('Page', {}).get('activities', [])
    return activities



@app.route('/activity')
def activity():
    username = request.cookies.get('username')
    access_token = request.cookies.get('access_token')

    if not username or not access_token:
        return redirect(url_for('login'))

    filter = request.args.get('filter', 'following')
    page = int(request.args.get('page', 1))
    per_page = 20
    following = filter == 'following'

    activities = fetch_activity(access_token, following=following, page=page, per_page=per_page)


    next_page = None
    if len(activities) == per_page:
        next_page = page + 1

    prev_page = page - 1 if page > 1 else None

    return render_template(
        'activity.html',
        username=username,
        current_filter=filter,
        activities=activities,
        page=page,
        next_page=next_page,
        prev_page=prev_page
    )



@app.route('/like/<int:activity_id>')
def like(activity_id):
    access_token = request.cookies.get('access_token')

    query = '''
    mutation ($id: Int, $type: LikeableType) {
      ToggleLikeV2(id: $id, type: $type) {
        ... on ListActivity {
          id
          isLiked
          likeCount
        }
        ... on TextActivity {
          id
          isLiked
          likeCount
        }
        ... on MessageActivity {
          id
          isLiked
          likeCount
        }
      }
    }
    '''
    variables = {
        'id': activity_id,
        'type': 'ACTIVITY'
    }

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables}, headers=headers)

    if response.status_code == 200:
        return redirect(url_for('activity'))
    else:
        print(f"Error toggling like: {response.status_code} - {response.text}")
        return f"Error: {response.status_code} - {response.json().get('errors')}"

@app.route('/comment/<int:activity_id>', methods=['GET'])
def comment(activity_id):
    access_token = request.cookies.get('access_token')
    comment_text = request.args.get('comment')

    if not comment_text:
        return "Error: Comment text cannot be empty", 400


    sanitized_comment_text = comment_text.replace('<', '&lt;').replace('>', '&gt;')

    query = '''
    mutation ($activityId: Int, $text: String) {
      SaveActivityReply(activityId: $activityId, text: $text) {
        id
        text
        likeCount
        createdAt
      }
    }
    '''
    variables = {
        'activityId': activity_id,
        'text': sanitized_comment_text
    }

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    response = requests.post(ANILIST_API_URL, json={'query': query, 'variables': variables}, headers=headers)

    if response.status_code == 200:
        return redirect(url_for('activity'))
    else:
        print(f"Error saving comment: {response.status_code} - {response.text}")
        return f"Error: {response.status_code} - {response.json().get('errors')}"


@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    from datetime import datetime
    return datetime.fromtimestamp(value).strftime(format)



def get_profile_info(username):
    access_token = request.cookies.get('access_token')
    query = '''
    query($username: String){
      User(name: $username){
        name
        avatar {
          large
        }
        bannerImage
        createdAt
        isFollowing
        isFollower
        about
        favourites{
          characters {
            nodes {
              id
              name {
                userPreferred
              }
              image {
                medium
              }
            }
          }
          anime {
            nodes {
              id
              title {
                userPreferred
              }
              coverImage {
                medium
              }
            }
          }
          manga {
            nodes {
              id
              title {
                userPreferred
              }
              coverImage {
                medium
              }
            }
          }
          studios {
            nodes {
              id
              name
            }
          }
          staff {
            nodes {
              id
              name {
                userPreferred
              }
              image {
                medium
              }
            }
          }
        }
      }
    }
    '''
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    variables = {
        "username": username
    }

    try:
        response = requests.post('https://graphql.anilist.co', json={'query': query, 'variables': variables}, headers=headers)
        response.raise_for_status()
        data = response.json()
        final = data.get('data', {}).get('User', {})
        return final
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}, 500

@app.route('/user', methods=['GET'])
def user():
    username = request.args.get('u')
    cookieuser = request.cookies.get('username')
    if not username:
        return {"error": "Username is required"}, 400

    data = get_profile_info(username)
    if "error" in data:
        return data, 500

    try:
        return render_template('user.html', data=data, cookieuser=cookieuser)
    except Exception as e:
        return {"error": str(e)}, 500
