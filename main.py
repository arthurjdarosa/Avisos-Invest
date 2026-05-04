# Imports
import os
from fastapi import FastAPI
import yfinance as yf
import requests
from dotenv import load_dotenv
import httpx

load_dotenv()
app = FastAPI()

@app.get("/")
async def verificar_investimentos():
    # Garante que o .env foi lido com sucesso.
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    ticker = "MXRF11.SA"

    dados = yf.download(ticker, period="6mo", progress=False)
    
    if dados.empty:
        return{"Status": "Erro", "mensagem": "Não foi possivel baixar dados da B3"}

    # Logica financeira
    preco_atual = float(dados['Close'].iloc[-1].values[0] if hasattr(dados['Close'].iloc[-1], 'values') else dados['Close'].iloc[-1])
    media_90_series = dados['Close'].rolling(window=90).mean().iloc[-1]
    media_90 = float(media_90_series.values[0] if hasattr(media_90_series, 'values') else media_90_series)

    # Alerta
    status_alerta =  "Preço acima da media. Nenhuma ação necessária"

    if preco_atual >= media_90:
        msg = (f"Oportunidade: {ticker}\n\n"
               f"Preço Atual: R$ {preco_atual:.2f}\n"
               f"Média 90 dias: R$ {media_90:.2f}\n")

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}

        async with httpx.AsyncClient() as client:
                await client.post(url, json=payload)
        status_alerta = "Alerta enviado para o Telegram!"
        
        return {
            "ticker": ticker,
            "preco_atual": round(preco_atual, 2),
            "media_90": round(media_90, 2),
            "resultado": status_alerta
        }