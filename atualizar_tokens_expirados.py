from dotenv import load_dotenv
load_dotenv()  # Carrega as variáveis do .env

import os
import datetime
from db import get_connection, save_athlete
from utils import refresh_token

def atualizar_tokens_expirados():
    print("🔁 Buscando atletas para atualização de tokens...")

    total_atualizados = 0

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT athlete_id, refresh_token FROM athletes")
                atletas = cur.fetchall()

        for atleta in atletas:
            try:
                data = refresh_token(atleta['refresh_token'])
                save_athlete(data)

                firstname = str(data['athlete'].get('firstname', '')).encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                lastname = str(data['athlete'].get('lastname', '')).encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
                nome = f"{firstname} {lastname}"
                print(f"✔ Token atualizado: {nome}")
                total_atualizados += 1

            except Exception as e:
                print(f"⚠ Erro ao atualizar token do atleta {atleta['athlete_id']}: {str(e)}")

    except Exception as e:
        print(f"❌ Erro geral na atualização: {str(e)}")

    print(f"✅ Tokens atualizados: {total_atualizados}")
    return total_atualizados
