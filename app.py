import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, redirect, request, jsonify

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

from utils import exchange_token

app = Flask(__name__)

@app.route("/")
def home():
    return "CareFit Strava API rodando!"

@app.route("/authorize")
def authorize():
    url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        "&approval_prompt=force"
        "&scope=read,activity:read_all"
    )
    return redirect(url)

@app.route("/debug-vars")
def debug_vars():
    return {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI
    }

@app.route("/env-vars")
def env_vars():
    return dict(os.environ)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Erro: código não recebido", 400

    token_data = exchange_token(code)
    return jsonify(token_data)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)