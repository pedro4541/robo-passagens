# ✈️ Robô de passagens: Orlando, abril/2027

Todo dia de manhã o robô consulta o Google Flights, grava o menor preço de ida e volta em
`historico.csv` e te avisa no Telegram quando:

- 🎯 o preço fica abaixo do seu **preço-alvo**;
- 📉 bate o **menor preço já registrado**;
- ⬇️ cai mais de X% desde a consulta anterior.

O gráfico fica em `index.html`. Para vê-lo no navegador, ligue o GitHub Pages em
**Settings → Pages → Branch: `main` / `(root)` → Save** e acesse
<https://pedro4541.github.io/robo-passagens/>.

## Como ligar (uns 10 minutos)

### 1. Chave da SerpApi (busca no Google Flights)
1. Crie uma conta grátis em <https://serpapi.com>.
2. Copie a **API Key** em *Dashboard → Api Key*.

> O plano grátis tem um limite de buscas por mês (veja no painel). Cada linha de `buscas`
> no `config.json` gasta 1 busca por dia: 2 combinações de datas ≈ 60 buscas/mês.

### 2. Bot do Telegram (avisos no celular; opcional, mas recomendado)
1. No Telegram, fale com **@BotFather** → `/newbot` → escolha um nome → copie o **token**.
2. Mande qualquer mensagem (ex.: "oi") para o seu bot novo.
3. Abra no navegador `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates` e copie o número em
   `"chat":{"id": ...}`: esse é o seu **chat id**.

### 3. Guardar as chaves no GitHub
No repositório: **Settings → Secrets and variables → Actions → New repository secret** e crie:

| Nome | Valor |
|---|---|
| `SERPAPI_KEY` | chave da SerpApi |
| `TELEGRAM_BOT_TOKEN` | token do BotFather |
| `TELEGRAM_CHAT_ID` | seu chat id |

### 4. Ajustar a viagem
Edite `config.json`: aeroporto de origem, datas de ida e volta, nº de adultos e
crianças, preço-alvo (valor **total** para todos os passageiros). Pode ter várias
combinações de datas para comparar.

### 5. Testar
Aba **Actions → Robô de passagens → Run workflow**. Em ~1 minuto chega a primeira mensagem no
Telegram e o `historico.csv` é criado. Depois disso ele roda sozinho todo dia às 08:17.


## Rodar no próprio computador
```bash
export SERPAPI_KEY=...            # e, se quiser, TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
python3 robo.py
```
Não precisa instalar nada além do Python 3.
