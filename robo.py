#!/usr/bin/env python3
"""Robô que acompanha o preço de passagens aéreas (Google Flights via SerpApi).

Para cada busca do config.json ele:
  1. consulta o menor preço de ida e volta (o Google devolve o total de todos
     os passageiros; o robô divide e trabalha com o preço POR PESSOA);
  2. grava uma linha em historico.csv;
  3. manda mensagem no Telegram se o preço caiu, bateu o mínimo histórico
     ou ficou abaixo do preço-alvo.

Variáveis de ambiente:
  SERPAPI_KEY         chave da https://serpapi.com (obrigatória)
  TELEGRAM_BOT_TOKEN  token do bot do Telegram (opcional)
  TELEGRAM_CHAT_ID    seu chat id no Telegram (opcional)

Só usa a biblioteca padrão do Python: nada para instalar.
"""
import csv
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PASTA = Path(__file__).resolve().parent
CONFIG = PASTA / "config.json"
HISTORICO = PASTA / "historico.csv"
COLUNAS = [
    "data_consulta", "busca", "origem", "destino", "ida", "volta",
    "preco", "preco_total", "moeda", "companhia", "paradas", "duracao_min",
    "nivel_preco", "faixa_tipica_min", "faixa_tipica_max",
]


def buscar_voos(cfg, busca, chave):
    params = {
        "engine": "google_flights",
        "departure_id": busca["origem"],
        "arrival_id": busca["destino"],
        "outbound_date": busca["ida"],
        "return_date": busca["volta"],
        "type": 1,  # ida e volta
        "currency": cfg.get("moeda", "BRL"),
        "hl": "pt",
        "gl": "br",
        "adults": cfg.get("adultos", 1),
        "children": cfg.get("criancas", 0),
        "travel_class": cfg.get("classe", 1),
        "api_key": chave,
    }
    if cfg.get("max_paradas"):
        params["stops"] = cfg["max_paradas"]
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=90) as resp:
        dados = json.load(resp)
    if "error" in dados:
        raise RuntimeError(dados["error"])
    return dados


def melhor_opcao(dados):
    """Retorna (preço, companhia, paradas, duração) da opção mais barata."""
    opcoes = [o for o in dados.get("best_flights", []) + dados.get("other_flights", [])
              if isinstance(o.get("price"), (int, float))]
    insights = dados.get("price_insights", {})
    if not opcoes:
        if insights.get("lowest_price"):
            return insights["lowest_price"], "", "", ""
        return None
    o = min(opcoes, key=lambda x: x["price"])
    trechos = o.get("flights", [])
    companhias = sorted({t.get("airline", "") for t in trechos if t.get("airline")})
    return o["price"], " / ".join(companhias), max(len(trechos) - 1, 0), o.get("total_duration", "")


def ler_historico():
    if not HISTORICO.exists():
        return []
    with HISTORICO.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gravar(linha):
    novo = not HISTORICO.exists()
    with HISTORICO.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo:
            w.writeheader()
        w.writerow(linha)


def brl(v):
    return "R$ " + f"{float(v):,.0f}".replace(",", ".")


def avisar_telegram(texto):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("  (Telegram não configurado, só imprimindo)")
        return
    corpo = urllib.parse.urlencode({"chat_id": chat, "text": texto, "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", corpo, timeout=30)


def motivos_de_alerta(cfg, preco, anteriores):
    motivos = []
    alvo = cfg.get("preco_alvo_por_pessoa")
    if alvo and preco <= alvo:
        motivos.append(f"🎯 chegou no seu alvo de {brl(alvo)}")
    if anteriores:
        ultimo = float(anteriores[-1]["preco"])
        minimo = min(float(a["preco"]) for a in anteriores)
        queda = (ultimo - preco) / ultimo * 100
        if preco < minimo:
            motivos.append(f"📉 menor preço já registrado (antes: {brl(minimo)})")
        elif queda >= cfg.get("avisar_queda_percentual", 3):
            motivos.append(f"⬇️ caiu {queda:.1f}% desde a última consulta ({brl(ultimo)})")
    else:
        motivos.append("🆕 primeira consulta desta busca")
    return motivos


def main():
    chave = os.environ.get("SERPAPI_KEY")
    if not chave:
        sys.exit("Defina a variável SERPAPI_KEY (crie grátis em https://serpapi.com).")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    historico = ler_historico()
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    alertas, falhas = [], 0

    for busca in cfg["buscas"]:
        print(f"→ {busca['nome']}")
        try:
            dados = buscar_voos(cfg, busca, chave)
            resultado = melhor_opcao(dados)
        except Exception as e:  # segue para a próxima busca
            print(f"  erro: {e}")
            falhas += 1
            continue
        if not resultado:
            print("  nenhum voo encontrado")
            continue
        total, companhia, paradas, duracao = resultado
        pessoas = max(cfg.get("adultos", 1) + cfg.get("criancas", 0), 1)
        preco = round(total / pessoas)
        ins = dados.get("price_insights", {})
        faixa = [round(v / pessoas) for v in (ins.get("typical_price_range") or [])] or ["", ""]
        print(f"  {brl(preco)}/pessoa (total {brl(total)})  {companhia}  paradas={paradas}  nível={ins.get('price_level', '?')}")

        anteriores = [h for h in historico if h["busca"] == busca["nome"]]
        motivos = motivos_de_alerta(cfg, preco, anteriores)
        if motivos:
            link = ("https://www.google.com/travel/flights?hl=pt-BR&curr=BRL&q="
                    + urllib.parse.quote(f"voos {busca['origem']} para {busca['destino']} "
                                         f"{busca['ida']} volta {busca['volta']}"))
            nivel = {"low": "baixo", "typical": "normal", "high": "alto"}.get(ins.get("price_level"), "")
            alertas.append(
                f"✈️ <b>{busca['nome']}</b>\n<b>{brl(preco)} por pessoa</b> (total {brl(total)})\n"
                f"{html.escape(companhia) or 'várias'} · "
                + ("voo direto" if paradas == 0 else f"{paradas} parada(s)") + "\n" + "\n".join(motivos)
                + (f"\nGoogle diz que o preço está <b>{nivel}</b>" if nivel else "")
                + (f" (normal: {brl(faixa[0])} a {brl(faixa[1])} por pessoa)" if faixa[0] else "")
                + f"\n<a href=\"{html.escape(link)}\">Ver no Google Flights</a>"
            )

        gravar({
            "data_consulta": agora, "busca": busca["nome"], "origem": busca["origem"],
            "destino": busca["destino"], "ida": busca["ida"], "volta": busca["volta"],
            "preco": preco, "preco_total": total, "moeda": cfg.get("moeda", "BRL"), "companhia": companhia,
            "paradas": paradas, "duracao_min": duracao, "nivel_preco": ins.get("price_level", ""),
            "faixa_tipica_min": faixa[0], "faixa_tipica_max": faixa[1],
        })

    for a in alertas:
        print("\n" + a)
        avisar_telegram(a)
    if falhas == len(cfg["buscas"]):
        sys.exit("Todas as buscas falharam.")


if __name__ == "__main__":
    main()
