"""Règles de signal d'entrée (stratégie de référence de D3).

Extrait de backtest/walk_forward.py (point de revue 7) pour séparer la RÈGLE
de trading de l'ORCHESTRATION du walk-forward. walk_forward.py réexporte
`generer_signaux_entree` : les anciens imports continuent de fonctionner.
"""

import pandas as pd
# Colonne portant le signal calculé UNE FOIS sur la série continue (voir ajouter_signaux).
COLONNE_SIGNAL_ENTREE = "signal_entree"


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


def ajouter_signaux(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute la colonne ``signal_entree`` calculée sur la série CONTINUE.

    Pourquoi : appliquée à une tranche (fenêtre train ou test), ``generer_signaux_entree`` ne
    connaît pas la bougie précédant la tranche. Sa première bougie est donc traitée comme si le
    Close « précédent » était sous la SMA : si le prix est déjà au-dessus de la SMA, un croisement
    inexistant est déclaré. Sur le PACK ES (fenêtres 250/60), 47 des 70 fenêtres test démarraient
    ainsi sur un faux signal.

    Calculer le signal une seule fois sur toute la série, puis découper, supprime ce défaut sans
    aucune fuite d'information : le signal en t n'utilise que des données jusqu'à t (test
    ``test_le_signal_a_l_instant_t_ne_depend_pas_du_futur``).
    """
    resultat = df.copy()
    resultat[COLONNE_SIGNAL_ENTREE] = generer_signaux_entree(df)
    return resultat