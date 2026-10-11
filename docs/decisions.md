# Décisions techniques — Piste Quantitatif DINIKA

Chaque décision est numérotée, datée et **assumée** (jamais cachée). Les choix marqués
« à valider » restent soumis à l'encadreur.

## D-001 — Couverture mesurée sur le code moteur uniquement
`audit/` et `paper_trading/` contiennent leurs `test_*.py` au même niveau que le code :
ils sont exclus de la mesure (`[tool.coverage.run] omit`). Les blocs
`if __name__ == "__main__"` (démos CLI) sont exclus. Seuil : 75 % (CDC).

## D-002 — Instruments réels vs synthétiques (point 4)
`InstrumentConfig.origine_donnees` : `REEL_GELE` (ES, pack v1.0 vérifié SHA-256) ou
`SYNTHETIQUE` (GOLD, fixtures). Défaut = `SYNTHETIQUE`. Aucun résultat « réel » ne doit
être annoncé pour un instrument synthétique.

## D-003 — Écart ATR/RSI entre D2 et le CSV de la Piste Data (point 29)
Constaté par test sur les 4453 lignes : SMA-20 identique (écart < 1e-9) ; EMA-20 converge
(< 0,01 après 100 bougies) ; ATR-14 et RSI-14 diffèrent en valeur (D2 : lissage de Wilder
via pandas_ta ; Piste Data : moyenne simple, corrélation 0,98 / 0,87).
Décision : D2 reste calculé de façon **indépendante** (les colonnes dérivées du CSV ne sont
jamais chargées dans `Bougie`). **À valider** avec l'encadreur : convention de référence.

## D-004 — D8 utilise le paramètre calibré par D3 (point 11)
`simuler_paper_trading_hors_echantillon` calibre le multiplicateur ATR sur la zone de
validation (via `calibrer_multiplicateur_atr`), l'applique à la zone hors-échantillon et
l'expose dans `multiplicateur_atr_utilise`. Aucune donnée hors-échantillon n'influence la
calibration (test dédié).

## D-005 — Règle de signal isolée (point 7)
`strategy/rules.py` porte `generer_signaux_entree` ; `walk_forward.py` la réexporte.

## D-006 — Dimanches conservés (point 28)
Aucun filtre par jour de semaine. Test : 744 bougies du dimanche présentes sur 4453.

## D-007 — Position ouverte en fin de fenêtre (à valider)
Une position encore ouverte à la fin d'un DataFrame n'est pas comptée comme trade
(simplification assumée, documentée dans `simuler_trades`).

## D-008 — TLS (exigence CDC non-fonctionnelle)
Le service FastAPI reste en HTTP sur le réseau Docker interne ; le chiffrement est assuré par un
reverse-proxy Caddy (`docker-compose.tls.yml`, `deploy/Caddyfile`), seul point exposé (80/443).
Certificat local auto-signé en dev, Let's Encrypt automatique si `DINIKA_DOMAINE` est un vrai domaine.
**Limite assumée** : configuration testée structurellement uniquement (pas d'exécution Docker dans
l'environnement de développement) ; à valider par un `docker compose -f docker-compose.tls.yml up`
avant la recette J5. Le journal d'audit et les clés en variables d'environnement restent inchangés.

## D-009 — Sharpe et drawdown : tranché par l'encadreur (journalier annualisé √252, equity)
**Défaut initialement corrigé** : l'ancienne formule divisait la chute (en POINTS) par `max(|sommet de
PnL cumulé en points|, 1)`. Quand le sommet était proche de 0, le résultat était en réalité un nombre de
points, affiché ensuite comme un pourcentage (constaté sur le pack réel : « drawdown 333,8 », soit
33 379 % à l'écran).

**Décision finale de l'encadreur** (remplace la version précédente de cette section) :
- **Sharpe** : rendements **journaliers** de la courbe d'equity (en dollars, PnL réellement dimensionné
  par D4), annualisé par **`√252`** (jours de bourse par an) — `backtest/metrics.py::calculer_sharpe_annualise`,
  constante `JOURS_TRADING_PAR_AN = 252`.
- **Drawdown** : calculé sur la **courbe d'equity en dollars** (pas sur un capital normalisé à 1) —
  `calculer_drawdown_equity`. Reste un ratio sans unité dans `[0, 1]`, mais reflète maintenant le compte
  réel (capital courant, taille en contrats entiers, coûts de transaction), pas une hypothèse de
  « 100 % investi sans levier ».
- La courbe d'equity est construite trade par trade dans `backtest/equity.py` à partir du capital
  résolu par D-012 (`config.instruments.resoudre_capital_virtuel`) et du dimensionnement réel de D4.
- Taux de réussite et nombre de trades sont inchangés (comptés sur le PnL en points, indépendamment de
  l'equity).

## D-013 — Bug corrigé : le dimensionnement ne suivait pas le capital courant
En connectant D-009 (equity) à D-012 (capital configurable), un bug a été trouvé dans
`backtest/simulator.py::simuler_trades` : chaque nouvelle entrée était dimensionnée avec le paramètre
`capital_virtuel` d'origine (jamais mis à jour), et non avec `capital_courant` (capital initial + PnL déjà
réalisés), qui était pourtant calculé (`capital_courant += pnl_dollars`) mais jamais relu. Le sizing ne
compoundait donc jamais au sein d'une même simulation. Corrigé : `calculer_risque(..., capital_courant,
...)`. Impact limité sur ES avec 2 M$ de capital (le compoundage change peu la taille), mais le
comportement correspond maintenant à ce que documente le module.

## D-010 — L'origine des données annoncée suit la source réellement lue
`/provenance/{id}` et le journal d'audit annonçaient `reel_gele` pour ES en mode `dev`, alors que les
données venaient de fixtures (version et SHA-256 vides). Corrigé : `dev` → toujours `synthetique` ;
`pack` → `reel_gele` + version + SHA-256 ; `prod` → origine de la config, sans hash (l'API Data n'en fournit pas).

## D-011 — Panneau D7 sur le pack réel : fenêtre de 1000 bougies et capital saisissable
Le walk-forward sur les 4453 bougies dure ~4,5 s (> seuil CDC de 3 s). Le panneau travaille donc sur les
1000 dernières bougies du pack (~4 ans) : limite affichée à l'écran, et mesurée par test (< 3 s).
Le capital virtuel est saisissable dans le panneau (valeur par défaut : D-012).

## D-012 — Dimensionnement d'ES : tranché par l'encadreur (capital configurable, contrat standard)
**Problème constaté** : avec l'ancien capital par défaut (10 000 $) et 1 % de risque par trade, le risque
autorisé était 100 $, alors que le risque d'UN contrat ES dépasse 7 000 $. La taille entière (règle non
négociable) tombait à 0 : ni signal dimensionné, ni trade en paper-trading.

**Décision finale de l'encadreur** :
- **Capital virtuel configurable**, par instrument, avec trois niveaux de priorité (`config/instruments.py`,
  `resoudre_capital_virtuel` / `resoudre_capital_portefeuille`) :
  1. valeur explicite passée par l'appelant (paramètre `capital_virtuel` de l'API, champ du panneau) ;
  2. variable d'environnement `DINIKA_CAPITAL_VIRTUEL` (déploiement) ;
  3. défaut par instrument, `InstrumentConfig.capital_virtuel_defaut`.
- **Contrat ES standard** (pas de micro-contrat MES) : `multiplicateur_contrat = 50`, inchangé.
- **1 % de risque par trade**, inchangé (`ParametresRisque.pourcentage_risque_par_trade`).
- **Sizing automatique**, inchangé : `taille = floor(risque_max_dollars / risque_par_contrat)` (D4).
- Le défaut d'ES est fixé à **2 000 000 $** dans `config/instruments.py` : c'est la valeur la plus basse
  qui garde une taille ≥ 1 sur la quasi-totalité des trades historiques du pack réel, avec le contrat
  standard et 1 % de risque — donc le résultat mécanique des quatre points ci-dessus, pas un choix libre.
  Le défaut de GOLD (synthétique) reste 10 000 $.
- Le panneau D7 explique toujours un « 0 contrat » avec les chiffres (`dashboard/synthese.py`), pour les
  cas où l'utilisateur choisit lui-même un capital plus faible.


## D-014 — Points d'amélioration indépendants de l'encadreur (A1, A3, A4, A5, A6)
- **A1 — Alertes D7 (< 5 s)** : `dashboard/alertes.py`, `generer_alertes()`. Signale un drawdown élevé,
  un Sharpe très négatif, une taille nulle, un ATR indisponible, trop peu de trades, ou un écart de
  réconciliation — chronométré et testé sous le seuil CDC de 5 s (`test_generer_alertes_prouve_le_critere_cdc_moins_de_5_secondes`).
  Les seuils (`SEUIL_DRAWDOWN_*`, `SEUIL_SHARPE_NEGATIF`, `NB_TRADES_MINIMUM_FIABLE`) sont des valeurs de
  travail, comme les autres seuils du projet : à valider par l'encadreur.
- **A3 — Disponibilité mesurable** : `HEALTHCHECK` dans le `Dockerfile` (interroge `/health` sans dépendance
  supplémentaire) et `restart: unless-stopped` sur tous les services (`docker-compose.yml`,
  `docker-compose.tls.yml`). Rend l'état "healthy/unhealthy" visible (`docker ps`) et permet un redémarrage
  automatique après un crash. Ne prouve pas un SLA de 99 % (cela dépend de l'hébergement), mais le rend
  mesurable et partiellement auto-réparant.
- **A4 — Versions figées** : `requirements-core.txt` passe de bornes `>=` à des versions exactes (`==`),
  celles testées par la suite complète. `requirements-vectorbt.txt` reste en borne minimale (jamais
  installée en pratique : absente de la CI et de l'image Docker).
- **A5 — PEP8 et docstrings** : `ruff` inclut désormais `W` et `D` (convention Google), avec
  `per-file-ignores` sur les tests. `ruff check .` passe sans exception.
- **A6 — Couverture** : 99,2 % globale (contre 96,7 % avant ces points). `main.py`, `config/instruments.py`
  et `scripts/generer_rapport_backtest.py` sont à 100 %. Reste 10 lignes non couvertes, toutes dans des
  branches d'affichage Streamlit ou de garde-fou peu risquées (`dashboard/panel_quant.py`,
  `paper_trading/portfolio.py`, `indicators/incremental.py`) — rendement décroissant au-delà.
