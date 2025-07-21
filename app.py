import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, redirect, request, jsonify

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")

from utils import exchange_token

app = Flask(__name__)

import pandas as pd
from flask import send_file
from io import BytesIO

import json

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Erro: código não recebido", 400

    token_data = exchange_token(code)

    # Pega dados do atleta
    athlete = token_data.get("athlete", {})
    atleta_id = athlete.get("id")

    # Cria estrutura para salvar
    dados_salvos = {
        "athlete_id": atleta_id,
        "nome": f"{athlete.get('firstname')} {athlete.get('lastname')}",
        "cidade": athlete.get("city"),
        "estado": athlete.get("state"),
        "peso": athlete.get("weight"),
        "access_token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "expires_at": token_data.get("expires_at"),
        "data_autorizacao": datetime.utcnow().isoformat()
    }

    # Salva em arquivo (um por atleta)
    path = f"athletes/{atleta_id}.json"
    os.makedirs("athletes", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados_salvos, f, ensure_ascii=False, indent=2)

    return jsonify({
        "mensagem": "Autorização realizada com sucesso! Atleta salvo.",
        "athlete": dados_salvos
    })


@app.route("/export-csv")
def export_csv():
    access_token = request.args.get("access_token")
    if not access_token:
        return {"error": "access_token não fornecido"}, 400

    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return {"error": "Erro ao buscar atividades", "details": response.json()}, response.status_code

    activities = response.json()
    df = pd.DataFrame(activities)

    # Filtrando apenas as colunas úteis
    colunas_desejadas = [
        'name', 'distance', 'moving_time', 'elapsed_time',
        'start_date', 'total_elevation_gain',
        'average_speed', 'max_speed', 'type'
    ]
    df = df[colunas_desejadas]

    # Convertendo distância de metros para km e tempo de segundos para minutos
    df['distance_km'] = df['distance'] / 1000
    df['moving_time_min'] = df['moving_time'] / 60
    df['elapsed_time_min'] = df['elapsed_time'] / 60

    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(output, mimetype='text/csv', download_name='atividades_strava.csv', as_attachment=True)


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
import requests

@app.route("/activities")
def get_activities():
    access_token = request.args.get("access_token")  # ou use um token fixo para teste
    if not access_token:
        return {"error": "access_token não fornecido"}, 400

    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return {"error": "Erro ao buscar atividades", "details": response.json()}, response.status_code

    return response.json()

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