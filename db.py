import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def save_athlete(token_data):
    athlete = token_data["athlete"]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO athletes (
                    athlete_id, firstname, lastname, city, state, sex, weight,
                    access_token, refresh_token, expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (athlete_id) DO UPDATE SET
                    firstname = EXCLUDED.firstname,
                    lastname = EXCLUDED.lastname,
                    city = EXCLUDED.city,
                    state = EXCLUDED.state,
                    sex = EXCLUDED.sex,
                    weight = EXCLUDED.weight,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at = EXCLUDED.expires_at;
            """, (
                athlete["id"], athlete["firstname"], athlete["lastname"],
                athlete.get("city"), athlete.get("state"), athlete.get("sex"), athlete.get("weight"),
                token_data["access_token"], token_data["refresh_token"], token_data["expires_at"]
            ))
            conn.commit()
