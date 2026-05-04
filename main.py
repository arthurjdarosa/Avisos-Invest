# Imports
import os
from fastapi import FastAPI
import yfinance as yf
import requests
from dotenv import load_dotenv
import httpx

load_dotenv()

app = FastAPI()

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

@app.get("/")
async def enviar_oi():
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "Oi! O FastAPI está online e te mandando um salve! 🚀"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)
    
    return {"status": "Mensagem enviada!", "telegram_response": response.json()}