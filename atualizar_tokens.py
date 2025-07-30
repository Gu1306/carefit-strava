from dotenv import load_dotenv
load_dotenv()

import os
import requests
import psycopg2
from datetime import datetime

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# ✅ Função alternativa de conexão segura (sem RealDictCursor)
def get_raw_connection():
    db_url = os.getenv("DATABASE_URL")
    conn = psycopg2.connect(db_url)
    conn.set_client_encoding('LATIN1')  # ⚠️ Força PostgreSQL a aceitar caracteres mal salvos
    return conn

def renovar_token(refresh_token):
    response = requests.post("https://www.strava.com/oauth/token", data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    })

    if response.status_code != 200:
        raise Exception(f"Erro {response.status_code}: {response.text}")

    return response.json()


def atualizar_tokens_expirados():
    print("🔁 Buscando atletas com token expirado...")

    atualizados = 0
    erros = []
    atletas = []

    try:
        with get_raw_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, athlete_id, refresh_token, expires_at
                    FROM athletes
                """)
                rows = cur.fetchall()
                for row in rows:
                    try:
                        id_local = row[0]
                        athlete_id = row[1]
                        refresh_token = row[2]
                        expires_at = row[3]

                        # Se refresh_token vier como bytes, tenta decodificar
                        if isinstance(refresh_token, bytes):
                            refresh_token = refresh_token.decode('utf-8', errors='replace')

                        atletas.append({
                            "id": id_local,
                            "athlete_id": athlete_id,
                            "refresh_token": refresh_token,
                            "expires_at": expires_at
                        })
                    except Exception as err:
                        print(f"❌ ERRO AO LER athlete_id={row[1]}: {err}")
                        erros.append((row[1], str(err)))

    except Exception as e:
        print("❌ ERRO GERAL ao acessar o banco:", str(e))
        return

    for atleta in atletas:
        id_local = atleta["id"]
        athlete_id = atleta["athlete_id"]
        refresh_token = atleta["refresh_token"]
        expires_at = atleta["expires_at"]

        print(f"🎯 Verificando athlete_id={athlete_id}...")

        if expires_at < datetime.now().timestamp():
            print(f"⏳ Token expirado — tentando renovar...")

            try:
                dados = renovar_token(refresh_token)

                novo_access_token = dados['access_token']
                novo_refresh_token = dados['refresh_token']
                novo_expires_at = dados['expires_at']

                with get_raw_connection() as conn2:
                    with conn2.cursor() as cur2:
                        cur2.execute("""
                            UPDATE athletes
                            SET access_token = %s,
                                refresh_token = %s,
                                expires_at = %s
                            WHERE id = %s
                        """, (novo_access_token, novo_refresh_token, novo_expires_at, id_local))
                        conn2.commit()

                atualizados += 1
                print(f"✅ Token atualizado com sucesso para athlete_id={athlete_id}")

            except Exception as e:
                print(f"❌ ERRO AO ATUALIZAR athlete_id={athlete_id}: {e}")
                erros.append((athlete_id, str(e)))
        else:
            print(f"⏩ Token ainda válido para athlete_id={athlete_id}")

    print("\n🎯 Atualização concluída.")
    print(f"✔ Tokens atualizados: {atualizados}")
    if erros:
        print(f"⚠ Erros em {len(erros)} atletas:")
        for err in erros:
            print(f" - ID {err[0]}: {err[1]}")


if __name__ == "__main__":
    atualizar_tokens_expirados()
