import os
import requests

def exchange_token(code):
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    redirect_uri = os.getenv("REDIRECT_URI")

    print("Trocando token com:")
    print("client_id:", client_id)
    print("client_secret:", "[OCULTO]")
    print("code:", code)
    print("redirect_uri:", redirect_uri)

    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        },
        timeout=10
    )

    print("Resposta do Strava:", response.status_code)
    print("Body:", response.text)

    response.raise_for_status()
    return response.json()
