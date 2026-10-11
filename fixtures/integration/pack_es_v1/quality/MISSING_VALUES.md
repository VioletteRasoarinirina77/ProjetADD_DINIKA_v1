# Gestion des valeurs manquantes
Dataset : `ES_quant_daily_v1.0.csv`
Version : `1.0`
## Règle générale
Les valeurs manquantes ne sont pas remplacées silencieusement par zéro, une interpolation ou une valeur précédente.
Les valeurs absentes dans les champs de marché obligatoires constituent une anomalie à contrôler.
Open Interest et Settlement peuvent être absents lorsque la source ne fournit pas de valeur exploitable pour la date concernée. Ces valeurs sont conservées comme `NaN`.
## Valeurs manquantes par colonne
| Colonne | Valeurs manquantes |
|---|---:|
| `timestamp` | 0 |
| `source` | 0 |
| `instrument_id` | 0 |
| `contract_instrument_id` | 0 |
| `open` | 0 |
| `high` | 0 |
| `low` | 0 |
| `close` | 0 |
| `volume` | 0 |
| `open_interest` | 108 |
| `settlement_price` | 95 |
| `cumulative_adjustment_factor` | 0 |
| `return_1d` | 0 |
| `return_5d` | 0 |
| `return_20d` | 0 |
| `log_return` | 0 |
| `sma_5` | 0 |
| `sma_20` | 0 |
| `sma_50` | 0 |
| `ema_20` | 0 |
| `ema_50` | 0 |
| `close_vs_sma20_pct` | 0 |
| `close_vs_sma50_pct` | 0 |
| `true_range` | 0 |
| `atr_14` | 0 |
| `volatility_20` | 0 |
| `rsi_14` | 0 |
| `volume_change` | 0 |
| `volume_sma_20` | 0 |
| `volume_ratio` | 0 |
| `oi_change` | 213 |
| `oi_change_pct` | 213 |
| `oi_sma_20` | 1851 |
| `daily_range` | 0 |
| `daily_range_pct` | 0 |
| `price_position` | 0 |

## Colonnes marché obligatoires
- `timestamp` : obligatoire ; valeurs manquantes = 0
- `open` : obligatoire ; valeurs manquantes = 0
- `high` : obligatoire ; valeurs manquantes = 0
- `low` : obligatoire ; valeurs manquantes = 0
- `close` : obligatoire ; valeurs manquantes = 0
- `volume` : obligatoire ; valeurs manquantes = 0

## Colonnes complémentaires
- `open_interest` : complémentaire ; valeurs manquantes = 108
- `settlement_price` : complémentaire ; valeurs manquantes = 95

## Indicateurs dérivés
Les indicateurs dérivés peuvent contenir des valeurs manquantes au début de la série lorsqu'une fenêtre d'observation est nécessaire au calcul. Ces valeurs ne doivent pas être confondues avec une absence de donnée OHLCV source.
