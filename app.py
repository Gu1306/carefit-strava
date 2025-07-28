from flask import Flask, request, jsonify
import os
from utils import exchange_token

app = Flask(__name__)

athletes_memory = []

@app.route("/")
def home():
    return "CareFit Strava API v2"

@app.route("/authorize")
def authorize():
    client_id = os.getenv("CLIENT_ID")
    redirect_uri = os.getenv("REDIRECT_URI")
    return (
        f"https://www.strava.com/oauth/authorize?client_id={client_id}"
        f"&response_type=code&redirect_uri={redirect_uri}"
        f"&scope=activity:read_all&approval_prompt=force"
    )

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Erro: código não recebido", 400

    try:
        token_data = exchange_token(code)
        print("TOKEN RECEBIDO:")
        print(token_data)
        return jsonify(token_data)
    except Exception as e:
        print("Erro no callback:", str(e))
        return f"Erro interno ao processar callback: {str(e)}", 500

@app.route("/athletes")
def list_athletes():
    return jsonify(athletes_memory)

if __name__ == "__main__":
    app.run(debug=True)
