## Bibliotecas

* **import os**: Interagir com o sistema.
* **from dotenv import load_dotenv**: Carregar o arquivo `.env` que carrega minhas chaves (como tokens).
* **from fastapi import FastAPI, HTTPException**: Importa a classe principal do framework FastAPI para criar a aplicação web e o manipulador de exceções HTTP.
* **from starlette.concurrency import run_in_threadpool**: Executa funções síncronas em uma thread separada para evitar o travamento do *event loop* assíncrono do FastAPI. Como o FastAPI é um framework assíncrono (`async def`) e o `yfinance` não é assíncrono, se chamar a função `yf.download` direto de um endpoint `async`, o FastAPI fica em choque e para. A solução é o `run_in_threadpool(coletar_dados_lote, TICKERS)`, que pega essa função e joga para ser executada em um módulo secundário (uma thread paralela do processador). Então meio que ele é a ponte.
* **import httpx**: Cliente HTTP assíncrono usado para fazer requisições à API do Telegram sem bloquear a aplicação.
* **import yfinance as yf**: Biblioteca para buscar cotações e histórico financeiro diretamente do Yahoo Finance.

---

## Inicializações

* **load_dotenv()**: Executa a leitura do arquivo `.env`.
* **app = FastAPI()**: Cria a instância da API. A variável `app` passa a ser a central do projeto e ela vai registrar quais URLs existem no sistema, tipo o `@app.get("/")` que eu estava usando para dar um ver se estava funcionando e o outro `@app.get("/check-invest")`. Como estou rodando na Vercel, ele procura a variável `app` para saber como rotear as requisições.
* **TICKERS = [...]**: Lista estática de ativos a serem monitorados na B3.

---

## Função de Coleta (`coletar_dados_lote`)

* **tickers_validos = [t for t in tickers if t.strip()]**: Operador `in` que percorre cada item `t` presente na lista `tickers`. Filtra elementos mantendo textos que não estejam vazios.
* **if not tickers_validos**: Valida se a lista ficou vazia; se sim, interrompe retornando `None`.
* **yf.download(...)**: Baixa o histórico que eu selecionei (`period="6mo"`) para todos os ativos em uma única chamada.

---

## Rota Principal (`/` e `/check-invest`)

* **Decoradores `@app.get(...)`**: Mapeia requisições HTTP GET nas rotas principais (`/` e `/check-invest`).
* **if not token or not chat_id**: Verifica a credencial. Retorna `True` se pelo menos uma das condições for verdadeira. Se faltar o `token` OU o `chat_id`, a API interrompe a execução e retorna uma resposta JSON de erro.

---

## Processamento dos Dados Financeiros

* **run_in_threadpool(...)**: Delega o download dos dados para uma thread secundária.
* **if dados is None or dados.empty**: Usa o `or` para checar se o download falhou totalmente ou se deu um DataFrame vazio.

---

## Cálculos e Regras de Negócio

* **fechamentos.rolling(window=90).mean().iloc[-1]**: Calcula a média móvel simples dos últimos 90 dias úteis.
* **desconto = ((media_90 - preco_atual) / media_90) * 100**: Calcula a variação percentual do preço atual em relação à média de 90 dias com um cálculo de padaria.
* **if preco_atual < (media_90 * 0.50)**: Aqui calcula 50% da média dos últimos 90 dias. Se for a metade, o código entende como queda crítica/anormal.
* **elif preco_atual < media_90**: Oportunidade de compra (preço atual está abaixo da média) e adiciono em formato HTML correspondente à lista `oportunidades_compra`.
* **else**: Preço acima da média (situação neutra). Como está dentro do `if/elif`, ele vai desconsiderar conforme a ordem de prioridade definida.

---

## Notificação via Telegram

* **Montagem da mensagem**: Unifica os blocos de texto gerados com `"\n".join(...)`.
* **if mensagens_para_enviar**: Se houver qualquer alerta (compra ou venda), prepara o envio HTTP POST para a API do Telegram usando o `httpx.AsyncClient()`.
* **Tratamento de Erros HTTP**: O bloco `try/except httpx.HTTPStatusError` captura falhas de envio sem derrubar o servidor.