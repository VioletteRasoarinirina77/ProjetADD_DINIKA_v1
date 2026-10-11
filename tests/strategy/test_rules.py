"""Tests de strategy/rules.py (point de revue 7)."""

import pandas as pd

from backtest import walk_forward
from strategy import rules


def _df(closes, smas):
    return pd.DataFrame({"close": closes, "sma_20": smas})


def test_signal_uniquement_au_croisement_haussier():
    signaux = rules.generer_signaux_entree(_df([9, 11, 12, 8, 11], [10, 10, 10, 10, 10]))
    assert signaux.tolist() == [False, True, False, False, True]


def test_pas_de_signal_quand_le_prix_reste_sous_la_moyenne():
    signaux = rules.generer_signaux_entree(_df([5, 6, 7], [10, 10, 10]))
    assert not signaux.any()


def test_le_signal_a_l_instant_t_ne_depend_pas_du_futur():
    """Anti look-ahead : tronquer la série après t ne change pas le signal en t."""
    df = _df([9, 11, 12, 8, 11], [10, 10, 10, 10, 10])
    complet = rules.generer_signaux_entree(df)
    tronque = rules.generer_signaux_entree(df.iloc[:3])
    assert complet.iloc[:3].tolist() == tronque.tolist()


def test_walk_forward_reexporte_la_meme_fonction():
    assert walk_forward.generer_signaux_entree is rules.generer_signaux_entree
