# Méthodologie — Piste Quantitatif DINIKA

## Données
Pack officiel `DINIKA_ES_QUANT_PACK_v1_0` (ES, Daily, 4453 lignes, gelé). Le SHA-256 est
vérifié avant tout chargement (`integration/pack_repository.py`) ; un écart interrompt le
pipeline (`ErreurIntegritePack`). `open_interest` / `settlement_price` manquants restent
`None` (jamais imputés).

## D2 — Indicateurs
SMA, EMA, RSI, MACD, ATR calculés indépendamment (batch `technical.py`, incrémental
`incremental.py`). Périodes centralisées dans `config/instruments.py`.

## D3 — Walk-forward
Fenêtres [train][test] chronologiques. Le multiplicateur ATR est calibré sur train
(meilleur Sharpe parmi `CANDIDATS_MULTIPLICATEUR_ATR`) puis appliqué tel quel sur test ;
le résultat ne provient que des fenêtres test. Déterminisme par construction (règles
pures, aucun tirage aléatoire). Entrée à l'Open de t+1 ; SL prioritaire si SL et TP sont
touchés sur la même bougie ; coût = `spread_points` de la configuration.
Métriques (`backtest/metrics.py`) : taux de réussite ; Sharpe par trade (non annualisé) ; drawdown = ratio
sans unité sur courbe de capital normalisée (D-009). PnL en points, aucune conversion en dollars.
Rapport reproductible : `python -m scripts.generer_rapport_backtest` (version + SHA-256 du dataset inclus).

## D4 — Risque
Taille entière (`math.floor`), stop/TP par ATR, exposition plafonnée, risque / notionnel
séparés. Aucun paramètre en dur hors `config/`.

## D8 — Paper-trading hors-échantillon
Historique scindé en zone de validation (D3) et zone hors-échantillon (la plus récente).
Paramètre calibré sur la validation uniquement (D-004). Simulation en mémoire : aucun
ordre réel.

## Limites assumées
Stratégie de référence longue uniquement ; Sharpe non annualisé ; coûts simplifiés ;
questions ouvertes listées dans `docs/decisions.md`. Aide à la décision : aucune promesse
de gain.
