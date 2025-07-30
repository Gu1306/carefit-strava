from flask import Flask, request, jsonify, render_template_string, Response
from flask_apscheduler import APScheduler
from functools import wraps
import os
import requests
from utils import exchange_token, refresh_token
from db import save_athlete, get_connection
import datetime
import pytz
import html
import base64
from atualizar_tokens import atualizar_tokens_expirados

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'Toktok*11')

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@scheduler.task("cron", id="tokens_06h", hour=6, timezone="America/Sao_Paulo")
def job_6h():
    atualizar_tokens_expirados()

@scheduler.task("cron", id="tokens_13h", hour=13, timezone="America/Sao_Paulo")
def job_13h():
    atualizar_tokens_expirados()

def check_auth(password):
    return password == "Toktok*11"

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.password):
            return Response("Acesso restrito à CareFit.\n", 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

@app.route("/painel")
@requires_auth
def painel_tokens():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT firstname, lastname, athlete_id, access_token, refresh_token, expires_at FROM athletes ORDER BY firstname")
                atletas = cur.fetchall()

        html_content = "<h2>Tokens dos Atletas - CareFit</h2><table border='1'><tr><th>Nome</th><th>ID</th><th>Link Strava</th><th>Access Token</th><th>Refresh Token</th><th>Expira Em</th></tr>"
        for a in atletas:
            nome_link = f"<a href='/atividades/{a['access_token']}' target='_blank'>{a['firstname']} {a['lastname']}</a>"
            strava_link = f"<a href='https://www.strava.com/athletes/{a['athlete_id']}' target='_blank'>🔗 Perfil</a>"
            expira = datetime.datetime.fromtimestamp(a["expires_at"])
            html_content += f"<tr><td>{nome_link}</td><td>{a['athlete_id']}</td><td>{strava_link}</td><td>{a['access_token']}</td><td>{a['refresh_token']}</td><td>{expira}</td></tr>"

        html_content += "</table>"
        return render_template_string(html_content)

    except Exception as e:
        return f"Erro ao carregar painel: {str(e)}", 500

@app.route("/atividades/<token>")
@requires_auth
def ver_atividades(token):
    try:
        headers = {"Authorization": f"Bearer {token}"}
        page = 1
        atividades = []

        while True:
            response = requests.get(
                f"https://www.strava.com/api/v3/athlete/activities?per_page=200&page={page}",
                headers=headers,
                timeout=10
            )
            if response.status_code != 200:
                break

            page_data = response.json()
            if not page_data:
                break

            atividades.extend(page_data)
            page += 1

        if not atividades:
            return "Nenhuma atividade encontrada."

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT firstname, lastname FROM athletes WHERE access_token = %s", (token,))
                resultado = cur.fetchone()
                nome_atleta = f"{html.escape(resultado['firstname'])}_{html.escape(resultado['lastname'])}".replace(" ", "_") if resultado else "atleta"

        txt_content = "\n\n".join([str(a) for a in atividades])
        dados_codificados = base64.b64encode(txt_content.encode("utf-8")).decode("utf-8")
        data_atual = datetime.datetime.now().strftime("%d-%m-%Y")
        nome_arquivo = f"{nome_atleta}_treinos_{data_atual}.txt"

        limite_data = datetime.datetime.now() - datetime.timedelta(days=90)
        atividades_90dias = [a for a in atividades if datetime.datetime.strptime(a['start_date_local'][:10], "%Y-%m-%d") >= limite_data]

        maior_corrida = max((a for a in atividades_90dias if a['type'] == 'Run'), key=lambda x: x['distance'], default=None)
        maior_pedal = max((a for a in atividades_90dias if a['type'] == 'Ride'), key=lambda x: x['distance'], default=None)

        melhores = {}
        for alvo in [10, 15, 21, 25, 30, 35, 40, 42]:
            melhores[alvo] = min(
                (a for a in atividades_90dias if a['type'] == 'Run' and 0.99*alvo*1000 <= a['distance'] <= 1.01*alvo*1000),
                key=lambda x: x['moving_time'],
                default=None
            )

        html_content = "<h3>Resumo dos Últimos 90 Dias</h3>"
        if maior_corrida:
            dist_km = round(maior_corrida['distance']/1000, 2)
            nome_corrida = html.escape(maior_corrida['name'])
            html_content += f"<p><strong>🏃‍♂️ Maior corrida:</strong> {dist_km} km — {nome_corrida}</p>"
        if maior_pedal:
            dist_km = round(maior_pedal['distance']/1000, 2)
            nome_pedal = html.escape(maior_pedal['name'])
            html_content += f"<p><strong>🚴‍♂️ Maior pedal:</strong> {dist_km} km — {nome_pedal}</p>"

        html_content += "<h4>🏆 Melhores tempos por distância:</h4><ul>"
        for km, atividade in melhores.items():
            if atividade:
                tempo = str(datetime.timedelta(seconds=atividade['moving_time']))
                nome_atividade = html.escape(atividade['name'])
                html_content += f"<li>{km} km: {tempo} — {nome_atividade}</li>"
        html_content += "</ul>"

        html_content += f"""
        <br><form method="post" action="/baixar-txt" target="_blank">
            <input type="hidden" name="dados" value="{dados_codificados}">
            <input type="hidden" name="filename" value="{nome_arquivo}">
            <button type="submit">📄 Baixar Treinos Completos (.txt)</button>
        </form>
        """
        return render_template_string(html_content)

    except Exception as e:
        return f"Erro ao processar atividades: {str(e)}", 500

@app.route('/baixar-txt', methods=['POST'])
@requires_auth
def baixar_txt():
    dados_codificados = request.form['dados']
    filename = request.form['filename']
    dados_decodificados = base64.b64decode(dados_codificados).decode('utf-8')
    return Response(
        dados_decodificados,
        mimetype='text/plain',
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )
