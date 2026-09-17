import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from starlette.concurrency import run_in_threadpool
import httpx
import yfinance as yf

load_dotenv()
app = FastAPI()

TICKERS = ["MXRF11.SA", "SNCI11.SA", "TAEE11.SA"]

def coletar_dados_lote(tickers: list[str]):
    """Baixa os dados de todos os tickers de uma só vez."""
    tickers_validos = [t for t in tickers if t.strip()]
    if not tickers_validos:
        return None
    return yf.download(
        " ".join(tickers_validos),
        period="6mo",
        group_by="ticker",
        progress=False,
    )

@app.get("/")
@app.get("/check-invest")
async def verificar_investimentos():
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return {
            "status": "erro_configuracao",
            "has_token": bool(token),
            "has_chat_id": bool(chat_id),
            "mensagem": "Credenciais do Telegram nao encontradas no os.getenv"
        }

    dados = await run_in_threadpool(coletar_dados_lote, TICKERS)

    if dados is None or dados.empty:
        return {"status": "erro", "mensagem": "Não foi possível baixar dados da B3 no Yahoo Finance"}

    resultados = []
    avisos_venda_imediata = []
    oportunidades_compra = []

    for ticker in TICKERS:
        try:
            df_ticker = dados[ticker] if len(TICKERS) > 1 else dados
            if "Close" not in df_ticker:
                resultados.append({"ticker": ticker, "status": "coluna_close_ausente"})
                continue

            fechamentos = df_ticker["Close"].dropna()

            if fechamentos.empty or len(fechamentos) < 90:
                resultados.append({"ticker": ticker, "status": "dados_insuficientes"})
                continue

            preco_atual = float(fechamentos.iloc[-1])
            media_90 = float(fechamentos.rolling(window=90).mean().iloc[-1])
            desconto = ((media_90 - preco_atual) / media_90) * 100

            if preco_atual < (media_90 * 0.50):
                avisos_venda_imediata.append(
                    f"🔴 <b>{ticker}</b> 🔴\n"
                    f"  ⚠️ <b>AÇÃO: VENDER IMEDIATAMENTE</b>\n"
                    f"  Preço Atual: R$ {preco_atual:.2f}\n"
                    f"  Média 90d: R$ {media_90:.2f}\n"
                    f"  Queda Crítica: <b>{desconto:.2f}%</b> (abaixo de 50% da média)\n"
                )
                resultados.append({
                    "ticker": ticker,
                    "preco_atual": round(preco_atual, 2),
                    "media_90": round(media_90, 2),
                    "status": "ALERTA_CRITICO_VENDA"
                })

            elif preco_atual < media_90:
                oportunidades_compra.append(
                    f"• <b>{ticker}</b>\n"
                    f"  Preço: R$ {preco_atual:.2f} | Média 90d: R$ {media_90:.2f}\n"
                    f"  Desconto: <b>{desconto:.2f}%</b>\n"
                )
                resultados.append({
                    "ticker": ticker,
                    "preco_atual": round(preco_atual, 2),
                    "media_90": round(media_90, 2),
                    "oportunidade": "OPORTUNIDADE_COMPRA"
                })

            else:
                resultados.append({
                    "ticker": ticker,
                    "preco_atual": round(preco_atual, 2),
                    "media_90": round(media_90, 2),
                    "status": "NEUTRO"
                })

        except Exception as e:
            resultados.append({"ticker": ticker, "erro": str(e)})

    mensagens_para_enviar = []

    if avisos_venda_imediata:
        corpo_venda = "\n".join(avisos_venda_imediata)
        mensagens_para_enviar.append(
            f"🚨🚨🚨 <b>ALERTA VERMELHO: STOP LOSS / VENDA</b> 🚨🚨🚨\n\n"
            f"Os seguintes ativos desabaram para menos da metade da média de 90 dias:\n\n"
            f"{corpo_venda}"
        )

    if oportunidades_compra:
        corpo_compra = "\n".join(oportunidades_compra)
        mensagens_para_enviar.append(
            f"🔔 <b>Oportunidades de Compra Detectadas:</b>\n\n{corpo_compra}"
        )

    if mensagens_para_enviar:
        texto_final = "\n\n==========================\n\n".join(mensagens_para_enviar)
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": texto_final, "parse_mode": "HTML"}

        async with httpx.AsyncClient() as client:
            try:
                resposta = await client.post(url, json=payload)
                resposta.raise_for_status()
            except httpx.HTTPStatusError as err:
                return {
                    "status": "erro_telegram",
                    "detalhes_telegram": err.response.text,
                    "detalhes": resultados
                }

    return {
        "status": "sucesso",
        "total_monitorados": len(TICKERS),
        "vendas_criticas": len(avisos_venda_imediata),
        "oportunidades_encontradas": len(oportunidades_compra),
        "detalhes": resultados
    }