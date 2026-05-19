# Marvel Rivals · haechanie Analytics

Dashboard data-driven focado em um único jogador (haechanie) — gera plano de climb
quantificado, análise de counters, sinergia com teammates, precisão vs média global,
team comp aliada, e insights que você não enxerga jogando.

```
/                landing visual
/haechanie       dashboard completo (12 abas)
```

## Stack

Python 3.10+, Streamlit (multi-page), Pandas, Plotly. Dados puxados da
[MarvelRivalsAPI.com](https://marvelrivalsapi.com/) e cacheados em JSON local.

## O que o dashboard mostra

- **Plano de Climb** — MR atual, gap pra próxima divisão, partidas até subir, herói pra focar
  vs pra cortar, com impacto estimado em pp de win rate
- **Counters** — heróis inimigos que mais te derrotam vs presa fácil
- **Sinergia** — qualidade do time aliado vs inimigo (KDA dos 5 outros aliados),
  top/bottom teammates por WR conjunta
- **Composição** — 2-2-2 vs solo tank vs no support, WR por role que VOCÊ joga
- **Precisão** — hit rate por herói comparado com `session_hit_rate` global da API
- **MR (Rank Score)** — trajetória, MR ganho/perdido por vitória/derrota, assimetria
- **Heróis** — performance por herói, distribuição por role, concentração do pool
- **Mapas** — WR por mapa, heatmap hero × map, close games vs blowouts
- **Padrões temporais** — queda noturna, tilt pós-derrotas, fadiga em sessão
- **What If** — "se você evitasse madrugada + pausasse após 2 derrotas, ganharia ~X MR"
- **Insights** — recomendações em linguagem natural

## Setup local

```bash
pip install -r requirements.txt
cp .env.example .env  # cole sua chave da MarvelRivalsAPI
python fetch_haechanie.py  # baixa todos os dados (~3min)
python run.py             # dashboard em http://localhost:8501
```

### Re-fetch
Pra atualizar dados após novas partidas (rate limit de 30 min por jogador):

```bash
python fetch_haechanie.py
```

## Deploy (Streamlit Community Cloud)

1. Push deste repo pra GitHub (privado pode)
2. Vá em [share.streamlit.io](https://share.streamlit.io/)
3. New app → escolha o repo, branch `main`, main file: `app.py`
4. Em "Advanced settings" → Secrets, cole:
   ```toml
   MARVEL_RIVALS_API_KEY = "sua_chave_aqui"
   ```
   (opcional — o app já vem com snapshot dos dados em `data/haechanie/*.json`,
   só precisa da chave se você rodar `fetch_haechanie.py` remoto)
5. Deploy. URL pública vai ser `https://<seu-app>.streamlit.app`

## Estrutura

```
app.py                  # Landing page em /
pages/
  1_haechanie.py        # Dashboard em /haechanie
run.py                  # Launcher com fix de event loop pra Windows + Py3.12
fetch_haechanie.py      # One-shot fetcher: puxa tudo da API e salva em data/haechanie/

config.py               # Carrega .env (API_KEY, URLs)
api/client.py           # Cliente HTTP da MarvelRivalsAPI (usado pelo fetcher e pelo
                        # modo multi-jogador comentado em pages/1_haechanie.py)
storage/db.py           # SQLite (legacy, não usado no modo single-player)

data/
  loader.py             # Carrega todos os JSONs de haechanie em DataFrames
  __init__.py
  haechanie/
    profile.json
    match_history.json
    match_details/*.json     # 1 por partida — todos os 12 jogadores
    hero_info/*.json         # role, abilities, difficulty
    hero_stats/*.json        # benchmark global por herói (hit rate, KDA, etc)
    hero_leaderboard/*.json  # top 10 players globais por herói
    heroes_catalog.json
    maps_catalog.json
    game_versions.json, balances.json, patch_notes.json

analytics/
  overview.py, temporal.py, hero_pool.py, patterns.py, insights.py,
  ranked.py, efficiency.py, highlights.py, comparative.py, whatif.py,
  synergy.py        # NEW: teammate quality + per-match team analysis
  counters.py       # NEW: matchup vs cada herói inimigo
  composition.py    # NEW: team comp analysis (2-2-2, solo tank, etc)
  accuracy.py       # NEW: hit rate vs global
  climb_plan.py     # NEW: plano data-driven com impacto quantificado

ui/
  theme.py          # CSS injection + helpers de render
  labels.py         # Tradução PT-BR de colunas técnicas
assets/styles.css   # Tema Marvel Rivals (Orbitron + Rajdhani, glow effects)
```

## Por que `python run.py` em vez de `streamlit run`?

`run.py` força `WindowsSelectorEventLoopPolicy` antes de subir o Streamlit — evita
o bug de WebSocket keepalive em Python 3.12 no Windows que deixa a página em skeleton.
Em Linux/Mac (incl. Streamlit Cloud), qualquer um dos dois funciona.
