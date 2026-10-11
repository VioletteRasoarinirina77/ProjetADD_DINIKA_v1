"""Métriques D3 : taux de réussite, Sharpe annualisé, drawdown maximum sur equity.

Conventions figées (décision D-009, docs/decisions.md) :

- Taux de réussite : part des trades de PnL en POINTS strictement positif. Il mesure la qualité du
  signal et ne dépend donc ni du capital ni de la taille de position.
- Sharpe : moyenne / écart-type (échantillon, ddof = 1) des rendements JOURNALIERS de la courbe
  d'equity en dollars, multiplié par racine(252). Sans taux sans risque. Les jours sans position
  comptent (rendement nul), ce qui reflète l'exposition réelle du compte.
- Drawdown maximum : plus forte baisse de l'equity depuis son sommet précédent, en proportion de ce
  sommet (ratio dans [0, 1]). Il dépend du capital et du dimensionnement, contrairement au PnL en points.

Si la taille recommandée est 0 (capital trop faible pour un contrat), l'equity est plate : Sharpe 0 et
drawdown 0 sont alors le reflet fidèle d'un compte qui n'a rien risqué (voir alertes, D7).
"""

from __future__ import annotations

import numpy as np

from contracts.schemas import ValidationBacktest

__all__ = [
    "JOURS_TRADING_PAR_AN",
    "calculer_drawdown_equity",
    "calculer_metriques",
    "calculer_sharpe_annualise",
]

# Facteur d'annualisation retenu (D-009). Le pack ES contient aussi les séances du dimanche soir
# (~307 bougies/an) : racine(252) sous-estime légèrement le Sharpe annualisé (facteur ~1,10) ; le choix
# est assumé et documenté plutôt que de filtrer des bougies valides du contrat de données.
JOURS_TRADING_PAR_AN = 252


def _rendements_journaliers(equity: np.ndarray) -> np.ndarray:
    equity = np.asarray(equity, dtype=float)
    precedent = equity[:-1]
    rendements = np.zeros(len(precedent))
    valides = precedent > 0
    rendements[valides] = equity[1:][valides] / precedent[valides] - 1.0
    return rendements


def calculer_sharpe_annualise(equity: np.ndarray) -> float:
    """Sharpe journalier annualisé par racine(252) ; 0.0 si l'equity est constante ou trop courte."""
    rendements = _rendements_journaliers(equity)
    if len(rendements) < 2:
        return 0.0
    ecart_type = rendements.std(ddof=1)
    if ecart_type <= 0:
        return 0.0
    return float(rendements.mean() / ecart_type * np.sqrt(JOURS_TRADING_PAR_AN))


def calculer_drawdown_equity(equity: np.ndarray) -> float:
    """Drawdown maximum relatif (ratio dans [0, 1]) de la courbe d'equity."""
    equity = np.asarray(equity, dtype=float)
    if len(equity) == 0:
        raise ValueError("Impossible de calculer un drawdown sans equity.")
    sommet = np.maximum.accumulate(equity)
    if (sommet <= 0).any():
        raise ValueError("L'equity doit rester strictement positive au sommet (capital initial > 0).")
    return float(np.clip((sommet - equity) / sommet, 0.0, 1.0).max())


def calculer_metriques(trades: list[dict], equity: np.ndarray | None = None) -> ValidationBacktest:
    """Métriques principales du backtest : `equity` est la courbe de `backtest.equity.courbe_equity`."""
    if not trades:
        return ValidationBacktest(sharpe=None, drawdown_max=None, taux_reussite=None, nb_trades=0)
    if equity is None:
        raise ValueError("La courbe d'equity est obligatoire pour calculer Sharpe et drawdown (D-009).")

    pnls_points = np.array([float(trade["pnl_points"]) for trade in trades], dtype=float)
    taux_reussite = float((pnls_points > 0).sum() / len(pnls_points))

    return ValidationBacktest(
        sharpe=round(calculer_sharpe_annualise(equity), 3),
        drawdown_max=round(calculer_drawdown_equity(equity), 4),
        taux_reussite=round(taux_reussite, 3),
        nb_trades=len(trades),
    )
