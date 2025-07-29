import os
import datetime
from dotenv import load_dotenv
from db import get_connection, save_athlete
from utils import refresh_token

load_dotenv()  # Carrega as variáveis do .env

print("🔄 Atualizando tokens...")

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
    print(f"❌ Erro geral na atualização: {str(e)}")