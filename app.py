from flask import Flask, request, jsonify, render_template_string, Response
from flask_apscheduler import APScheduler
from functools import wraps
import os
import requests
from utils import exchange_token, refresh_token
from db import save_athlete, get_connection
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'Toktok*11')  # proteção simples

# ======= Agendador =======
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

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
                <th>Access Token</th>
                <th>Expira Em</th>
            </tr>
        """
        for a in atletas:
            nome_link = f"<a href='/atividades/{a['access_token']}' target='_blank'>{a['firstname']} {a['lastname']}</a>"
            expira = datetime.datetime.fromtimestamp(a["expires_at"])
            html += f"<tr><td>{nome_link}</td><td>{a['athlete_id']}</td><td>{a['access_token']}</td><td>{expira}</td></tr>"

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
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities?per_page=60",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            return f"Erro ao buscar atividades: {response.status_code}", 400

        atividades = response.json()
        if not atividades:
            return "Nenhuma atividade encontrada."

        linhas_txt = []
        html = "<h3>Últimos 60 treinos</h3><table border='1'><tr><th>Data</th><th>Nome</th><th>Distância (km)</th><th>Tempo (min)</th><th>Ritmo</th></tr>"
        for atividade in atividades:
            nome = atividade.get("name", "Sem título")
            distancia_km = round(atividade.get("distance", 0) / 1000, 2)
            duracao_min = round(atividade.get("elapsed_time", 0) / 60, 2)
            ritmo = f"{round((atividade.get('elapsed_time', 1) / 60) / (atividade.get('distance', 1) / 1000), 2)} min/km" if atividade.get('distance') else "-"
            data = atividade.get("start_date_local", "")[:10]

            html += f"<tr><td>{data}</td><td>{nome}</td><td>{distancia_km}</td><td>{duracao_min}</td><td>{ritmo}</td></tr>"
            linhas_txt.append(f"{data} | {nome} | {distancia_km} km | {duracao_min} min | {ritmo}")

        html += "</table>"
        txt_content = "\n".join(linhas_txt)

        html += f"""
        <br><form method="post" action="/baixar-txt" target="_blank">
            <input type="hidden" name="dados" value="{txt_content.replace('"', '&quot;')}">
            <input type="hidden" name="filename" value="treinos_{token}.txt">
            <button type="submit">📄 Baixar em TXT</button>
        </form>
        """
        return render_template_string(html)
    except Exception as e:
        return f"Erro ao processar atividades: {str(e)}", 500

@app.route("/baixar-txt", methods=["POST"])
def baixar_txt():
    dados = request.form.get("dados", "")
    filename = request.form.get("filename", "treinos.txt")
    return Response(dados, mimetype="text/plain", headers={"Content-Disposition": f"attachment;filename={filename}"})


 # ======= Rota manual para forçar atualização imediata dos tokens =======
@app.route("/forcar-atualizacao")
@requires_auth
def forcar_atualizacao_tokens():
    print("🔧 Atualização manual de tokens iniciada...")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT athlete_id, refresh_token FROM athletes")
                atletas = cur.fetchall()

        atualizados = []
        for atleta in atletas:
            try:
                data = refresh_token(atleta['refresh_token'])
                save_athlete(data)
                nome = f"{data['athlete']['firstname']} {data['athlete']['lastname']}"
                atualizados.append(nome)
                print(f"✔ Token atualizado: {nome}")
            except Exception as e:
                print(f"⚠ Erro ao atualizar token do atleta {atleta['athlete_id']}: {str(e)}")

        return f"Tokens atualizados com sucesso: {', '.join(atualizados)}", 200
    except Exception as e:
        return f"Erro ao atualizar tokens: {str(e)}", 500

# ======= Tarefa agendada: atualizar tokens todos os dias =======
@scheduler.task("cron", id="atualiza_tokens", hour=5)
def atualizar_tokens_expirados():
    print("⏰ Iniciando atualização automática de tokens...")
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT athlete_id, refresh_token FROM athletes")
                atletas = cur.fetchall()

        for atleta in atletas:
            try:
                data = refresh_token(atleta['refresh_token'])
                save_athlete(data)
                print(f"✔ Token atualizado: {data['athlete']['firstname']} {data['athlete']['lastname']}")
            except Exception as e:
                print(f"⚠ Erro ao atualizar token do atleta {atleta['athlete_id']}: {str(e)}")

    except Exception as e:
        print("❌ Erro ao atualizar tokens em massa:", str(e))

# ======= Rota já existente (mantida) =======
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
        save_athlete(token_data)
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
            "https://www.strava.com/api/v3/athlete/activities?per_page=60",
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
