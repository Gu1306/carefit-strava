from flask import Flask, render_template_string, request, Response
from db import get_connection  # Usa sua função atual de conexão ao PostgreSQL
import os

app = Flask(__name__)

USERNAME = "carefit"
PASSWORD = "Toktok*11"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Tokens - CareFit</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f9f9f9; }
        h1 { color: #333; }
        table { width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.05); }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Tokens de Atletas - CareFit</h1>
    <table>
        <tr>
            <th>Nome</th>
            <th>Token</th>
            <th>Refresh Token</th>
            <th>Expira em</th>
        </tr>
        {% for atleta in atletas %}
        <tr>
            <td>{{ atleta.firstname }} {{ atleta.lastname }}</td>
            <td>{{ atleta.access_token }}</td>
            <td>{{ atleta.refresh_token }}</td>
            <td>{{ atleta.expires_at }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""


def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
        'Autenticação necessária.', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


@app.route("/tokens")
@requires_auth
def mostrar_tokens():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT firstname, lastname, access_token, refresh_token, expires_at 
                FROM athletes ORDER BY lastname
            """)
            atletas = cur.fetchall()
    return render_template_string(HTML_TEMPLATE, atletas=atletas)


if __name__ == "__main__":
    app.run(debug=True)
