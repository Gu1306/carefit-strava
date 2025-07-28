from flask import Flask, request, jsonify
import os
import requests
from utils import exchange_token
from db import save_athlete, get_connection  # importa funções novas

app = Flask(__name__)

@app.route("/")
def home():
    return "CareFit Strava API v3 (banco de dados ativo)"

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
        save_athlete(token_data)  # grava no banco
        return "Autorizado e salvo com sucesso! Você já pode fechar esta aba."
    except Exception as e:
        print("Erro no callback:", str(e))
        return f"Erro interno ao processar callback: {str(e)}", 500

@app.route("/athletes")
def list_athletes():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT athlete_id, firstname, lastname, city, state, sex FROM athletes ORDER BY created_at DESC")
                athletes = cur.fetchall()
        return jsonify(athletes)
    except Exception as e:
        print("Erro ao listar atletas:", str(e))
        return "Erro ao acessar o banco", 500

@app.route("/activities")
def get_activities():
    token = request.args.get("token")
    if not token:
        return "Token ausente", 400

    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            print("Erro ao buscar atividades:", response.status_code, response.text)
            return f"Erro do Strava: {response.status_code}", 500

        activities = response.json()
        return jsonify(activities)

    except Exception as e:
        print("Erro ao buscar atividades:", str(e))
        return f"Erro interno: {str(e)}", 500

if __name__ == "__main__":
    app.run(debug=True)
