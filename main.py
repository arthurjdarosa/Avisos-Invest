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
     """Baixa os dados de todos os tickers de uma so vez."""
     tickers_validos = [t for t in tickers if t.strip()]
     if not tickers_validos:
          return None
     # yfinance baixa multiplos tickers separados por espaço
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
        raise HTTPException(
            status_code=500,
            detail="Credenciais do Telegram não configuradas no .env"
        )

    # Executa o yfinance em uma threadpool para não travar o FastAPI
    dados = await run_in_threadpool(coletar_dados_lote, TICKERS)

    if dados is None or dados.empty:
        return {"status": "erro", "mensagem": "Não foi possível baixar dados da B3"}

    resultados = []
    avisos_venda_imediata = []
    oportunidades_compra = []
    
    for ticker in TICKERS:
        try:
            # Com group_by='ticker', dados[ticker] traz o DataFrame individual
            df_ticker = dados[ticker] if len(TICKERS) > 1 else dados
            fechamentos = df_ticker["Close"].dropna()

            if fechamentos.empty or len(fechamentos) < 90:
                resultados.append({"ticker": ticker, "Status": "dados_insudicientes"})
                continue

            preco_atual = float(fechamentos.iloc[-1])
            media_90 = float(fechamentos.rolling(window=90).mean().iloc[-1])
            desconto = ((media_90 - preco_atual) / media_90) * 100

            # 1. Regra critica: menos da metade da media (< 50% de media_90)
            if preco_atual < (media_90 * 0.50):
                avisos_venda_imediata.append(
                    f"🔴 *{ticker}* 🔴\n"
                    f"  ⚠️ *AÇÃO: VENDER IMEDIATAMENTE*\n"
                    f"  Preço Atual: R$ {preco_atual:.2f}\n"
                    f"  Média 90d: R$ {media_90:.2f}\n"
                    f"  Queda Crítica: *{desconto:.2f}%* (abaixo de 50% da média)\n"
                )
                resultados.append({
                    "ticker": ticker,
                    "preco_atual": round(preco_atual, 2),
                    "media_90": round(media_90, 2),
                    "status": "ALERTA_CRITICO_VENDA"
                })

            elif preco_atual < media_90:
                oportunidades_compra.append(
                    f"• *{ticker}*\n"
                    f"  Preço: R$ {preco_atual:.2f} | Média 90d: R$ {media_90:.2f}\n"
                    f"  Desconto: *{desconto:.2f}%*\n"
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

    # Montagem da notificação
    mensagens_para_enviar = []
         
    if avisos_venda_imediata:
        corpo_venda = "\n".join(avisos_venda_imediata)
        mensagens_para_enviar.append(
            f"🚨🚨🚨 *ALERTA VERMELHO: STOP LOSS / VENDA* 🚨🚨🚨\n\n"
            f"Os seguintes ativos desabaram para menos da metade da média de 90 dias:\n\n"
            f"{corpo_venda}"
        )

    if oportunidades_compra:
        corpo_compra = "\n".join(oportunidades_compra)
        mensagens_para_enviar.append(
            f"🔔 *Oportunidades de Compra Detectadas:*\n\n{corpo_compra}"
        )

    # Envia via Telegram caso haja algo para alertar
    if mensagens_para_enviar:
        texto_final = "\n\n━━━━━━━━━━━━━━━━━━━━\n\n".join(mensagens_para_enviar)
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": texto_final, "parse_mode": "Markdown"}

        async with httpx.AsyncClient() as client:
            resposta = await client.post(url, json=payload)
            resposta.raise_for_status()

    return {
        "status": "sucesso",
        "total_monitorados": len(TICKERS),
        "vendas_criticas": len(avisos_venda_imediata),
        "oportunidades_encontradas": len(oportunidades_compra),
        "detalhes": resultados
    }