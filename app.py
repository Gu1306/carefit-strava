from flask import Flask, request, jsonify, render_template_string, Response
from flask_apscheduler import APScheduler
from functools import wraps
import os
import requests
from utils import exchange_token, refresh_token
from db import save_athlete, get_connection
import datetime
import pytz
from atualizar_tokens import atualizar_tokens_expirados

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'Toktok*11')  # proteção simples

# ======= Agendador =======
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

@scheduler.task("cron", id="tokens_06h", hour=6, timezone="America/Sao_Paulo")
def job_6h():
    print("⏰ [06:00] Atualizando tokens...")
    atualizar_tokens_expirados()

@scheduler.task("cron", id="tokens_13h", hour=13, timezone="America/Sao_Paulo")
def job_13h():
    print("⏰ [13:00] Atualizando tokens...")
    atualizar_tokens_expirados()

# ======= Função de autenticação básica =======
def check_auth(password):
    return password == "Toktok*11"

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.password):
            return Response(
                "Acesso restrito à CareFit.\n", 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'}
            )
        return f(*args, **kwargs)
    return decorated

# ======= Rota protegida para painel HTML =======
@app.route("/painel")
@requires_auth
def painel_tokens():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT firstname, lastname, athlete_id, access_token, refresh_token, expires_at
                    FROM athletes
                    ORDER BY firstname
                """)
                atletas = cur.fetchall()

        html = """
        <h2>Tokens dos Atletas - CareFit</h2>
        <table border='1'>
            <tr>
                <th>Nome</th>
                <th>ID</th>
                <th>Link Strava</th>
                <th>Access Token</th>
                <th>Refresh Token</th>
                <th>Expira Em</th>
            </tr>
        """
        for a in atletas:
            nome_link = f"<a href='/atividades/{a['access_token']}' target='_blank'>{a['firstname']} {a['lastname']}</a>"
            strava_link = f"<a href='https://www.strava.com/athletes/{a['athlete_id']}' target='_blank'>🔗 Perfil</a>"
            expira = datetime.datetime.fromtimestamp(a["expires_at"])
            html += f"<tr><td>{nome_link}</td><td>{a['athlete_id']}</td><td>{strava_link}</td><td>{a['access_token']}</td><td>{a['refresh_token']}</td><td>{expira}</td></tr>"

        html += "</table>"
        return render_template_string(html)

    except Exception as e:
        return f"Erro ao carregar painel: {str(e)}", 500

# ======= Rota para exibir e baixar as atividades =======
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
                nome_atleta = f"{resultado['firstname']}_{resultado['lastname']}".replace(" ", "_") if resultado else "atleta"

        html = "<h3>Resumo de atividades</h3><table border='1'><tr><th>Nome</th><th>Distância (km)</th><th>Tempo de Movimento</th><th>Tipo</th><th>Pace Médio</th><th>Elevação (m)</th><th>Data</th></tr>"
        linhas_txt = []
        maior_distancia = 0
        corrida_maior = None
        corridas_15k = 0

        for atividade in atividades:
            nome = atividade.get("name", "Sem título")
            distancia_km = round(atividade.get("distance", 0) / 1000, 2)
            tempo_movimento_seg = atividade.get("moving_time", 0)
            tempo_movimento_fmt = str(datetime.timedelta(seconds=tempo_movimento_seg))
            tipo = atividade.get("type", "Desconhecido")
            elevacao = round(atividade.get("total_elevation_gain", 0), 1)

            if atividade.get("distance"):
                pace = (tempo_movimento_seg / 60) / (atividade.get("distance") / 1000)
                pace_fmt = f"{int(pace)}:{int((pace % 1) * 60):02d} min/km"
            else:
                pace_fmt = "-"

            data_str = atividade.get("start_date_local", "")
            try:
                data_fmt = datetime.datetime.strptime(data_str[:16], "%Y-%m-%dT%H:%M").strftime("%d/%m/%Y - %H:%M")
            except:
                data_fmt = data_str

            html += f"<tr><td>{nome}</td><td>{distancia_km}</td><td>{tempo_movimento_fmt}</td><td>{tipo}</td><td>{pace_fmt}</td><td>{elevacao}</td><td>{data_fmt}</td></tr>"
            linhas_txt.append(str(atividade))

            if tipo == "Run":
                if distancia_km > maior_distancia:
                    maior_distancia = distancia_km
                    corrida_maior = nome
                if distancia_km >= 15:
                    corridas_15k += 1

        html += "</table>"
        html += f"<p><strong>🏅 Maior distância corrida:</strong> {maior_distancia} km ({corrida_maior})</p>"
        html += f"<p><strong>📈 Corridas com 15km ou mais:</strong> {corridas_15k}</p>"

        txt_content = "\n\n".join(linhas_txt)
        data_atual = datetime.datetime.now().strftime("%d-%m-%Y")
        nome_arquivo = f"{nome_atleta}_treinos_{data_atual}.txt"

        html += f"""
        <br><form method="post" action="/baixar-txt" target="_blank">
            <input type="hidden" name="dados" value="{txt_content.replace('"', '&quot;')}">
            <input type="hidden" name="filename" value="{nome_arquivo}">
            <button type="submit">📄 Baixar Treinos Completos (.txt)</button>
        </form>
        """
        return render_template_string(html)

    except Exception as e:
        return f"Erro ao processar atividades: {str(e)}", 500