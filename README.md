# DINIKA — Piste Quantitatif (D2 · D3 · D4)

Outil d'**aide à la décision** pour le trading sur contrats à terme (E PREST SOLUTIONS, ENI Fianarantsoa).
Aucune exécution d'ordre réel, aucune promesse de gain : un bandeau d'avertissement est affiché en
permanence dans le tableau de bord.

Cette piste fournit : les **indicateurs techniques** (D2), le **backtesting walk-forward** (D3) et la
**gestion du risque** (D4), plus la part commune **D7** (panneau) et **D8** (paper-trading hors-échantillon).

## 1. Démarrage rapide

```bash
python3.12 -m venv .venv && source .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -r requirements-core.txt

ruff check .                                   # lint
pytest                                         # tests + couverture (seuil 75 %)

streamlit run dashboard/panel_quant.py         # panneau D7 (pack réel ES par défaut)
ENVIRONMENT=pack uvicorn main:app --port 8002  # API FastAPI sur le pack réel (Windows : set ENVIRONMENT=pack)
python -m scripts.generer_rapport_backtest     # rapport D3 reproductible -> docs/rapport_backtest_ES_v1.0.md
```

Modes de l'API (`ENVIRONMENT`) : `dev` = fixtures synthétiques · `pack` = pack gelé ES v1.0 (SHA-256 vérifié) ·
`prod` = API de la Piste Data. Documentation interactive : `http://localhost:8002/docs`.

Docker : `docker compose up --build` (HTTP) ou `docker compose -f docker-compose.tls.yml up --build` (HTTPS via Caddy).

## 2. Ce que fait chaque livrable

| Livrable | Où | Ce qui est vérifié |
|---|---|---|
| D2 indicateurs | `indicators/` | SMA, EMA, RSI, MACD, ATR en batch **et** en incrémental à coût constant (< 5 s) ; recoupement avec le CSV de la Piste Data |
| D3 walk-forward | `backtest/`, `strategy/` | Fenêtres [train][test] ; calibration du multiplicateur ATR sur train seulement ; résultat issu des seules fenêtres test ; déterministe ; rapport reproductible |
| D4 risque | `risk/` | Taille en **entier** de contrats ; stop-loss / take-profit par ATR ; exposition et perte max ; aucun paramètre en dur hors `config/` |
| D7 panneau | `dashboard/` | Synthèse < 3 s (mesurée sur le pack réel) ; bandeau d'avertissement en haut de page ; origine des données affichée |
| D8 paper-trading | `paper_trading/` | Journal horodaté ; courbe de capital ; zone hors-échantillon étanche ; aucun ordre réel |
| Transverse | `audit/`, `integration/`, `main.py` | Journal d'audit JSON ; SHA-256 du dataset vérifié avant tout calcul ; clés en variables d'environnement |

Architecture détaillée : `docs/architecture.md`. Méthodologie : `docs/methodology.md`.

## 3. Données et traçabilité

Dataset officiel `DINIKA_ES_QUANT_PACK_v1_0` (ES, quotidien, 4453 bougies, 2012-02-29 → 2026-09-13), **gelé**,
SHA-256 `23af73a8a6160b45ead19c53503bf5ef56b1a010a63535297eecbc4b1dbb83ac`.

- `integration/pack_repository.py` recalcule le SHA-256 avant tout chargement ; en cas d'écart le pipeline
  s'arrête (`ErreurIntegritePack`, HTTP 503 côté API) plutôt que de calculer sur un fichier modifié.
- Les valeurs manquantes (`open_interest`, `settlement_price`) restent `None` : jamais imputées.
- Les 744 dimanches du dataset sont conservés : aucun filtre par jour de semaine.
- Chaque résultat (API `/provenance/{instrument}`, journal d'audit, rapport) porte la version du dataset
  et son SHA-256. L'origine annoncée (`reel_gele` / `synthetique`) suit la source **réellement** lue.
- GOLD ne dispose d'aucun pack réel : il n'existe qu'en fixtures synthétiques et n'est jamais présenté comme réel.

## 4. Résultats de référence (pack réel ES v1.0)

Stratégie de référence volontairement simple (croisement Close / SMA-20, long seul). Capital virtuel
**2 000 000 $** (D-012, valeur par défaut de l'instrument ES — voir `docs/decisions.md`), contrat standard,
1 % de risque par trade, taille dimensionnée automatiquement en contrats entiers (D4). Sharpe annualisé
sur rendements journaliers de l'equity (`√252`), drawdown sur la courbe d'equity en dollars (D-009).
Détail et définitions : `docs/rapport_backtest_ES_v1.0.md`.

| Train / Test | Trades | Taux de réussite | Sharpe (annualisé √252) | Drawdown max (equity) |
|---:|---:|---:|---:|---:|
| 60 / 20 | 125 | 18,4 % | −1,018 | 38,5 % |
| 250 / 60 | 106 | 36,8 % | 0,186 | 14,5 % |
| 500 / 120 | 93 | 36,6 % | 0,145 | 9,6 % |

Ces chiffres **valident l'outillage et le protocole hors-échantillon**, pas une stratégie rentable : la règle
de référence ne l'est pas, et le projet ne promet aucun gain.

## 5. Limites assumées et points à valider avec l'encadreur

Détail numéroté dans `docs/decisions.md`.

- **D-012 — Capital et ES : tranché.** Capital virtuel configurable (argument explicite → variable
  d'environnement `DINIKA_CAPITAL_VIRTUEL` → défaut par instrument), contrat ES standard, 1 % de risque,
  sizing automatique inchangés. Défaut d'ES fixé à 2 000 000 $ (résultat mécanique de ces règles sur
  l'historique réel, pas un choix libre). Le panneau explique toujours un « 0 contrat » avec les chiffres
  si l'utilisateur choisit lui-même un capital plus faible.
- **D-009 — Métriques : tranché.** Sharpe = rendements journaliers de l'equity, annualisé par `√252`.
  Drawdown = chute maximale de l'equity en dollars (capital réel, taille entière, coûts de transaction).
- **D-003 — ATR/RSI** : D2 (lissage de Wilder) et le CSV de la Piste Data (moyenne simple) diffèrent ; D2 reste indépendant.
- **D-007 — Position ouverte** en fin de fenêtre non comptée.
- **TLS (D-008)** : configuration Caddy validée structurellement, **jamais exécutée sous Docker** — à faire avant la recette J5.
- **Intégration** avec `piste-data` / `piste-ia` : services encore en placeholder dans `docker-compose.yml`.
- Le panneau D7 travaille sur les 1000 dernières bougies du pack (le walk-forward complet dépasse 3 s) — D-011.
- **Alertes D7** (`dashboard/alertes.py`) : drawdown élevé, Sharpe très négatif, taille nulle, ATR
  indisponible, peu de trades, écart de réconciliation — chronométrées et testées sous 5 s (D-014). Seuils
  de travail, à valider comme les autres seuils du projet.
- **Disponibilité** : `HEALTHCHECK` Docker + `restart: unless-stopped` (D-014) rendent l'état mesurable et
  partiellement auto-réparant, sans démontrer un SLA de 99 % (dépend de l'hébergement).

## 6. Choix de bibliothèques

pandas / numpy (séries temporelles), pandas-ta (indicateurs, pur Python), pydantic v2 (contrat inter-pistes),
FastAPI + uvicorn (service), Streamlit (panneau), pytest / pytest-cov / ruff (qualité). **TA-Lib écartée** :
compilation C source de blocages sans bénéfice ici. **vectorbt** (backtest multi-instruments) n'est utilisée par
aucun module : elle reste dans `requirements-vectorbt.txt`, hors de l'image Docker et de la CI.
scikit-learn / statsmodels sont réservées à D9 (Piste Data).
