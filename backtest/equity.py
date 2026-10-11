"""Courbe d'equity journalière D3 (décision D-009).

L'equity est la valeur du compte virtuel à la clôture de chaque bougie, en dollars :
    equity(t) = capital au début de la fenêtre
                + PnL des trades déjà clôturés à t (coût de transaction inclus)
                + PnL latent de la position ouverte à t, valorisée au Close de t (mark-to-market).

Une position encore ouverte à la fin de la fenêtre n'est pas un trade comptabilisé (D-007) : elle
n'apparaît donc pas non plus dans la courbe, ce qui garde la série continue d'une fenêtre à l'autre.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["courbe_equity"]


def courbe_equity(
    df: pd.DataFrame,
    trades: list[dict],
    capital_initial: float,
    multiplicateur_contrat: float,
) -> np.ndarray:
    """Equity à chaque bougie de `df`, précédée du capital initial (longueur = len(df) + 1).

    `trades` : sortie de `simuler_trades(df, ...)` (chronologique, sans chevauchement), chaque trade
    portant `entree_ts`, `sortie_ts`, `prix_entree`, `taille` et `pnl_dollars`.
    """
    closes = df["close"].to_numpy(dtype=float)
    equity = np.full(len(df), float(capital_initial))
    capital_realise = float(capital_initial)

    for trade in trades:
        i_entree = df.index.get_loc(trade["entree_ts"])
        i_sortie = df.index.get_loc(trade["sortie_ts"])
        latent = (closes[i_entree:i_sortie] - trade["prix_entree"]) * multiplicateur_contrat * trade["taille"]
        equity[i_entree:i_sortie] = capital_realise + latent
        capital_realise += trade["pnl_dollars"]
        equity[i_sortie:] = capital_realise

    return np.concatenate(([float(capital_initial)], equity))
