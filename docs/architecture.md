# Architecture — Piste Quantitatif DINIKA

```
config/        instruments.py : registre des instruments (ES, GOLD), paramètres de risque, périodes
contracts/     schemas.py : contrat Pydantic (Bougie, SignalQuantitatif, ValidationBacktest)
data/          repository.py : lecture des bougies via l'API de la Piste Data
integration/   pack_repository.py (pack gelé + SHA-256), charger_donnees_pack.py,
               verifier_contrat.py, reconciliation.py
indicators/    D2 : technical.py (batch), incremental.py (temps réel, coût constant)
strategy/      rules.py : règle de signal (croisement Close / SMA-20)
backtest/      D3 : simulator.py (trades), metrics.py (Sharpe / drawdown / réussite),
               walk_forward.py (découpage, calibration sur train, orchestration)
risk/          D4 : position_sizing.py, stops.py, exposure.py
services/      quant_engine.py : signal D2 + D4
paper_trading/ D8 (commun) : simulator.py hors-échantillon, portfolio.py multi-instruments
dashboard/     D7 (commun) : synthese.py (logique testée), panel_quant.py (Streamlit)
audit/         logger.py : journal d'audit JSON (exigence CDC non-fonctionnelle)
scripts/       generer_rapport_backtest.py : rapport reproductible
main.py        service FastAPI
```

Flux : Piste Data (pack gelé ou API) → `integration/` / `data/` → `indicators/` (D2) → `strategy/` +
`backtest/` (D3) et `risk/` (D4) → `services/quant_engine.py` → API `main.py` / panneau `dashboard/`.

## Écarts assumés par rapport à la structure cible du prompt
- `data/integrity.py` et `data/validators.py` n'existent pas : la vérification SHA-256 est dans
  `integration/pack_repository.py` (testée) et le contrôle qualité dans `integration/verifier_contrat.py`.
- `config/risk.py` et `config/settings.py` n'existent pas : `ParametresRisque` est dans `config/instruments.py`.
- `audit/` est conservé (exigence CDC), absent du schéma cible par oubli.
- Les fichiers `test_*.py` de `audit/` et `paper_trading/` sont au niveau du code (exclus de la couverture, D-001).


