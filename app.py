from flask import Flask, request, jsonify, render_template_string, Response
from flask_apscheduler import APScheduler
from functools import wraps
import os
import json  
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

@scheduler.task("cron", id="tokens_11h", hour=11, timezone="America/Sao_Paulo")
def job_11h():
    atualizar_tokens_expirados()
	
@scheduler.task("cron", id="tokens_16h", hour=16, timezone="America/Sao_Paulo")
def job_16h():
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
        profile_response = requests.get("https://www.strava.com/api/v3/athlete", headers=headers, timeout=10)
        athlete_profile = profile_response.json()

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
                cur.execute("SELECT firstname, lastname, athlete_id FROM athletes WHERE access_token = %s", (token,))
                resultado = cur.fetchone()
                nome_atleta_completo = f"{resultado['firstname']} {resultado['lastname']}"
                nome_atleta = f"{html.escape(resultado['firstname'])}_{html.escape(resultado['lastname'])}".replace(" ", "_") if resultado else "atleta"
                athlete_id = resultado['athlete_id'] if resultado else None


        pasta_saida = "arquivos_json"
        os.makedirs(pasta_saida, exist_ok=True)

        def salvar_json(nome_arquivo, dados):
            caminho = os.path.join(pasta_saida, nome_arquivo)
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)

        data_atual = datetime.datetime.now().strftime("%d-%m-%Y")
        nome_1_200 = f"{nome_atleta}_treinos_1_a_200_{data_atual}.json"
        nome_201_400 = f"{nome_atleta}_treinos_201_a_400_{data_atual}.json"
        nome_401_600 = f"{nome_atleta}_treinos_401_a_600_{data_atual}.json"
        nome_601_800 = f"{nome_atleta}_treinos_601_a_800_{data_atual}.json"
        nome_801_1000 = f"{nome_atleta}_treinos_801_a_1000_{data_atual}.json"

        salvar_json(nome_1_200, atividades[0:200] + [{"download_datetime": datetime.datetime.now().isoformat()}])
        salvar_json(nome_201_400, atividades[200:400] + [{"download_datetime": datetime.datetime.now().isoformat()}])
        salvar_json(nome_401_600, atividades[400:600] + [{"download_datetime": datetime.datetime.now().isoformat()}])
        salvar_json(nome_601_800, atividades[600:800] + [{"download_datetime": datetime.datetime.now().isoformat()}])
        salvar_json(nome_801_1000, atividades[800:1000] + [{"download_datetime": datetime.datetime.now().isoformat()}])

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


        foto_url = athlete_profile.get("profile", "")
        link_strava = f"https://www.strava.com/athletes/{athlete_id}" if athlete_id else "#"

        html_content = f"""
        <div style='display:flex; align-items:center; gap:10px;'>
            <img src='{foto_url}' alt='Foto' width='60' height='60' style='border-radius:50%;'>
            <div>
                <h2 style='margin:0; font-size: 20px;'>
                    <strong>{html.escape(nome_atleta_completo)}</strong>
                    <a href='{link_strava}' target='_blank'>🔗</a>
                </h2>
            </div>
        </div>
        """

        html_content += "<h3>Resumo dos Últimos 90 Dias</h3>"
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

        html_content += "<h4>📋 Treinos nos últimos 90 dias</h4>"
        html_content += "<table border='1'><tr><th>Nome</th><th>Distância (km)</th><th>Pace Médio</th><th>Tempo Total</th><th>Altimetria</th><th>Data</th></tr>"
        for a in atividades_90dias:
            nome = html.escape(a['name'])
            dist_km = round(a['distance']/1000, 2)
            moving_time = a['moving_time']
            pace = (moving_time / (a['distance']/1000)) if a['distance'] else 0
            pace_str = str(datetime.timedelta(seconds=int(pace))) if pace > 0 else '-'
            duracao = str(datetime.timedelta(seconds=moving_time))
            altimetria = a.get('total_elevation_gain', '-')
            data_atividade = a.get('start_date_local', '')[:10]
            html_content += f"<tr><td>{nome}</td><td>{dist_km}</td><td>{pace_str}</td><td>{duracao}</td><td>{altimetria}</td><td>{data_atividade}</td></tr>"
            
        html_content += "</table>"

        html_content += f"""
        <br>

	<a href="/download-json/{ nome_1_200 }" target="_blank" style="display:inline-block; margin-right:10px;">
   	    <button type="button">Treinos 1 a 200 (.json)</button>
	</a>

	<a href="/download-json/{ nome_201_400 }" target="_blank" style="display:inline-block; margin-right:10px;">
    	    <button type="button">Treinos 201 a 400 (.json)</button>
	</a>

	<a href="/download-json/{ nome_401_600 }" target="_blank" style="display:inline-block; margin-right:10px;">
    	    <button type="button">Treinos 401 a 600 (.json)</button>
	</a>

	<a href="/download-json/{ nome_601_800 }" target="_blank" style="display:inline-block; margin-right:10px;">
   	    <button type="button">Treinos 601 a 800 (.json)</button>
	</a>

	<a href="/download-json/{ nome_801_1000 }" target="_blank" style="display:inline-block;">
    		<button type="button">Treinos 801 a 1000 (.json)</button>
	</a>
        
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

@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        if not code:
            return "❌ Erro: código de autorização não encontrado."

        athlete_data = exchange_token(code)

        # ✅ Correção: passar o dicionário completo como espera o db.py
        save_athlete(athlete_data)

        return """
        <h2>✅ Tudo certo!</h2>
        <p>Sua conta Strava foi conectada com sucesso à CareFit.</p>
        <p>Agora podemos acompanhar seus treinos e cuidar ainda melhor da sua performance! 🧡</p>
        <a href='https://carefitclub.com.br'>← Voltar para o site</a>
        """
    except Exception as e:
        return f"❌ Erro ao processar autorização: {str(e)}"

@app.route("/atualizar-tokens-manualmente")
def atualizar_tokens_manual():
    chave = request.args.get("chave")
    if chave != os.getenv("SECRET_KEY"):
        return "🔒 Acesso não autorizado."

    try:
        from atualizar_tokens import atualizar_tokens_expirados
        total = atualizar_tokens_expirados()
        return f"✅ Atualização concluída! Tokens atualizados: {total}"
    except Exception as e:
        return f"❌ Erro ao atualizar tokens: {str(e)}"

from flask import send_from_directory

@app.route('/download-json/<filename>')
@requires_auth
def download_json(filename):
    pasta_saida = "arquivos_json"
    try:
        return send_from_directory(pasta_saida, filename, as_attachment=True)
    except FileNotFoundError:
        return f"❌ Arquivo '{filename}' não encontrado.", 404

