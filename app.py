from flask import Flask, redirect, request, url_for
import requests

app = Flask(__name__)

CLIENT_ID = '19938'
CLIENT_SECRET = 'NLS5w9OkV2RWyKDTLdTzLxy3oN1BRfCbbOZUa9RR'
REDIRECT_URI = 'http://127.0.0.1:5000/get'
ANILIST_AUTHORIZE_URL = 'https://anilist.co/api/v2/oauth/authorize'
ANILIST_TOKEN_URL = 'https://anilist.co/api/v2/oauth/token'

@app.route('/')
def home():
    return '<a href="/login">Login with AniList</a>'

@app.route('/login')
def login():
    auth_url = f"{ANILIST_AUTHORIZE_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code"
    return redirect(auth_url)

@app.route('/get')
def get_token():
    code = request.args.get('code')
    if code:
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'redirect_uri': REDIRECT_URI,
            'code': code,
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        response = requests.post(ANILIST_TOKEN_URL, json=token_data, headers=headers)
        if response.status_code == 200:
            access_token = response.json().get('access_token')
            return f"Access Token: {access_token}"
        else:
            return f"Error: {response.json()}"
    else:
        return "No code provided"

if __name__ == '__main__':
    app.run(debug=True)
