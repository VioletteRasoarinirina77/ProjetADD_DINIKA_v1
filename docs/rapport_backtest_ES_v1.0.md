# Rapport de backtest walk-forward — ES (D3)

- Généré le : 2026-09-30 02:24 UTC
- Dataset : version **1.0**, intégrité vérifiée : True
- SHA-256 : `23af73a8a6160b45ead19c53503bf5ef56b1a010a63535297eecbc4b1dbb83ac`
- Bougies : 4453 (2012-02-29 → 2026-09-13), quotidiennes, dimanches conservés
- Capital virtuel (D-012) : **2,000,000 $**, contrat ES standard, 1 % de risque par trade, taille dimensionnée automatiquement en nombre entier de contrats (D4)
- Stratégie : achat au croisement haussier Close / SMA-20, entrée à l'Open de t+1, stop et take-profit par ATR, position longue unique, coût = `spread_points` de la config
- Protocole : fenêtres glissantes [train][test] ; multiplicateur ATR calibré sur train uniquement ; résultat issu des seules fenêtres test

| Train | Test | Trades | Taux de réussite | Sharpe (annualisé √252) | Drawdown max (equity) |
|---:|---:|---:|---:|---:|---:|
| 60 | 20 | 125 | 18.4% | -1.018 | 38.5% |
| 250 | 60 | 106 | 36.8% | 0.186 | 14.5% |
| 500 | 120 | 93 | 36.6% | 0.145 | 9.6% |

## Lecture honnête

- Sharpe : rendements **journaliers** de la courbe d'equity, annualisé par **√252** (D-009, tranché par l'encadreur).
- Drawdown max : chute maximale de la courbe d'**equity en dollars** (capital réel, taille en contrats entiers, coûts de transaction), en proportion du sommet précédent (D-009).
- Position ouverte en fin de fenêtre : non comptée (D-007, à valider).
- Taux de réussite : calculé sur le PnL en points (indépendant du capital et de la taille).
- Ces chiffres valident le protocole et l'outillage. La stratégie de référence est volontairement simple ; aucun de ces résultats n'est une promesse de gain (outil d'aide à la décision).
