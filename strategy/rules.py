"""Règles de signal d'entrée (stratégie de référence de D3).

Extrait de backtest/walk_forward.py (point de revue 7) pour séparer la RÈGLE
de trading de l'ORCHESTRATION du walk-forward. walk_forward.py réexporte
`generer_signaux_entree` : les anciens imports continuent de fonctionner.
"""

import pandas as pd


def generer_signaux_entree(df: pd.DataFrame) -> pd.Series:
    """Génère les signaux d'entrée sur croisement haussier Close / SMA-20.

    Signal :
        Close[t] > SMA[t]
        ET
        Close[t-1] <= SMA[t-1]

    Le signal est calculé uniquement avec les informations disponibles
    à la clôture de la bougie t (aucune fuite du futur). L'entrée réelle est
    effectuée par simuler_trades() à l'Open de t+1.
    """
    au_dessus = df["close"] > df["sma_20"]

    # fill_value=False conserve une série booléenne et évite le type object
    # provoqué par un NaN au premier élément.
    au_dessus_precedent = au_dessus.shift(1, fill_value=False)

    return au_dessus & (~au_dessus_precedent)
