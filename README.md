# CareFit Strava API

API básica em Flask para integrar com o Strava e capturar os dados dos atletas autorizados.

## Rotas disponíveis

- `/authorize`: redireciona o atleta para o consentimento do Strava
- `/callback`: recebe o código do Strava e troca por token de acesso

## Como usar

1. Configure as variáveis de ambiente com base no arquivo `.env.example`
2. Instale as dependências com `pip install -r requirements.txt`
3. Rode com `python app.py`

🚀 Desenvolvido para deploy no Railway com GitHub
