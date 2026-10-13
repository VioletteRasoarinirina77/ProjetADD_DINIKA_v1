"""Tests de la correction D3 : le signal d'entrée est calculé sur la série CONTINUE.

Défaut corrigé : ``generer_signaux_entree`` appliquée à chaque tranche train/test déclarait un
croisement à la première bougie de la tranche dès que le Close était déjà au-dessus de la SMA
(la bougie précédente, hors tranche, était ignorée). Sur le PACK ES (250/60), 47 des 70 fenêtres
test commençaient par un faux signal.
"""

from pathlib import Path

import pandas as pd
import pytest

import backtest.walk_forward as walk_forward
import paper_trading.simulator as simulateur_d8
from backtest.simulator import simuler_trades
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from integration.pack_repository import PackDataRepository
from strategy.rules import COLONNE_SIGNAL_ENTREE, ajouter_signaux, generer_signaux_entree

PACK = Path(__file__).parents[2] / "fixtures" / "integration" / "pack_es_v1"


def _serie_synthetique() -> pd.DataFrame:
    """15 bougies : sous la SMA (0-4), VRAI croisement en 5, au-dessus jusqu'en 10, puis chute."""
    closes = [100] * 5 + [105] * 6 + [90, 90, 90, 90]
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "sma_20": [102.0] * 15,
            "atr_14": [5.0] * 15,
        },
        index=pd.date_range("2026-01-01", periods=15, freq="D", tz="UTC"),
    )


def test_ajouter_signaux_ajoute_la_colonne_sans_modifier_l_original():
    df = _serie_synthetique()
    resultat = ajouter_signaux(df)
    assert COLONNE_SIGNAL_ENTREE in resultat.columns
    assert COLONNE_SIGNAL_ENTREE not in df.columns
    assert resultat[COLONNE_SIGNAL_ENTREE].tolist() == generer_signaux_entree(df).tolist()


def test_une_tranche_seule_declare_un_faux_croisement_mais_pas_la_serie_continue():
    """C'est exactement le défaut : la tranche démarre au-dessus de la SMA, sans croisement réel."""
    continu = ajouter_signaux(_serie_synthetique())
    tranche_debut = continu.iloc[8:]  # fenêtre qui démarre déjà au-dessus de la SMA

    assert generer_signaux_entree(tranche_debut).iloc[0]  # recalcul sur la tranche : FAUX signal
    assert not tranche_debut[COLONNE_SIGNAL_ENTREE].iloc[0]  # signal hérité de la série : correct
    assert continu[COLONNE_SIGNAL_ENTREE].sum() == 1  # un seul vrai croisement, en bougie 5


def test_simuler_trades_ne_cree_aucune_position_au_bord_d_une_fenetre():
    """La tranche [8:] contient la chute vers 90 : avec le faux signal, un trade perdant serait ouvert."""
    tranche = ajouter_signaux(_serie_synthetique()).iloc[8:]
    assert simuler_trades(tranche, "GOLD", capital_virtuel=1_000_000.0) == []


def test_simuler_trades_prend_le_vrai_croisement_de_la_serie_continue():
    trades = simuler_trades(ajouter_signaux(_serie_synthetique()), "GOLD", capital_virtuel=1_000_000.0)
    assert len(trades) == 1
    assert trades[0]["entree_ts"] == _serie_synthetique().index[6]  # Open de la bougie suivant le signal


def test_simuler_trades_sans_colonne_se_comporte_comme_avant_pour_une_serie_complete():
    """Compatibilité : un DataFrame complet sans colonne de signal reste accepté (tests existants, D8)."""
    df = _serie_synthetique()
    avec = simuler_trades(ajouter_signaux(df), "GOLD", capital_virtuel=1_000_000.0)
    sans = simuler_trades(df, "GOLD", capital_virtuel=1_000_000.0)
    assert avec == sans


@pytest.fixture(scope="module")
def bougies_es():
    return PackDataRepository(PACK).candles_validees("ES")[:700]


def test_le_walk_forward_transmet_le_signal_continu_a_chaque_fenetre(bougies_es, monkeypatch):
    """Preuve d'intégration sur le PACK ES : train ET test reçoivent exactement le signal de la série."""
    complet = ajouter_signaux(ajouter_indicateurs(bougies_vers_dataframe(bougies_es), "ES"))
    appels = []
    reel = walk_forward.simuler_trades

    def espion(df, *args, **kwargs):
        appels.append(df)
        return reel(df, *args, **kwargs)

    monkeypatch.setattr(walk_forward, "simuler_trades", espion)
    walk_forward.walk_forward_backtest(bougies_es, "ES", 250, 60)

    assert appels, "le walk-forward doit simuler au moins une fenêtre"
    for tranche in appels:
        assert COLONNE_SIGNAL_ENTREE in tranche.columns
        attendu = complet.loc[tranche.index, COLONNE_SIGNAL_ENTREE]
        assert (tranche[COLONNE_SIGNAL_ENTREE] == attendu).all()


def test_d8_hors_echantillon_utilise_le_signal_continu(bougies_es, monkeypatch):
    recus = []
    reel = simulateur_d8.simuler_trades

    def espion(df, *args, **kwargs):
        recus.append(df)
        return reel(df, *args, **kwargs)

    monkeypatch.setattr(simulateur_d8, "simuler_trades", espion)
    simulateur_d8.simuler_paper_trading_hors_echantillon(bougies_es, "ES", taille_hors_echantillon=60)

    assert len(recus) == 1
    zone_hors_echantillon = recus[0]
    assert COLONNE_SIGNAL_ENTREE in zone_hors_echantillon.columns
    complet = ajouter_signaux(ajouter_indicateurs(bougies_vers_dataframe(bougies_es), "ES"))
    attendu = complet.loc[zone_hors_echantillon.index, COLONNE_SIGNAL_ENTREE]
    assert (zone_hors_echantillon[COLONNE_SIGNAL_ENTREE] == attendu).all()


# ---------------------------------------------------------------------------
# Sortie au gap (honnêteté des métriques)
# ---------------------------------------------------------------------------


def _scenario_gap(open_suivante: float, high: float, low: float) -> pd.DataFrame:
    """Entrée à 110 (Open de la bougie 1) ; ATR 5, GOLD k = 2 -> stop 100, take-profit 130."""
    return pd.DataFrame(
        {
            "open": [104, 110, open_suivante],
            "high": [106, 112, high],
            "low": [103, 108, low],
            "close": [105, 111, 100],
            "sma_20": [102.0] * 3,
            "atr_14": [5.0] * 3,
        },
        index=pd.date_range("2026-01-01", periods=3, freq="D", tz="UTC"),
    )


def test_gap_sous_le_stop_sort_a_l_open_et_non_au_prix_du_stop():
    trades = simuler_trades(_scenario_gap(open_suivante=95, high=96, low=94), "GOLD", 1_000_000.0)
    assert trades[0]["prix_sortie"] == pytest.approx(95.0)  # pire que le stop (100) : le gap est subi
    assert trades[0]["pnl_points"] < -15  # perte supérieure à la perte théorique du stop (-10 - coût)


def test_stop_touche_sans_gap_sort_au_prix_du_stop():
    trades = simuler_trades(_scenario_gap(open_suivante=108, high=109, low=99), "GOLD", 1_000_000.0)
    assert trades[0]["prix_sortie"] == pytest.approx(100.0)


def test_gap_au_dessus_du_take_profit_reste_execute_au_prix_du_take_profit():
    trades = simuler_trades(_scenario_gap(open_suivante=135, high=136, low=134), "GOLD", 1_000_000.0)
    assert trades[0]["prix_sortie"] == pytest.approx(130.0)  # pas de gain de gap comptabilisé


def test_stop_et_take_profit_sur_la_meme_bougie_le_stop_reste_prioritaire():
    trades = simuler_trades(_scenario_gap(open_suivante=108, high=131, low=99), "GOLD", 1_000_000.0)
    assert trades[0]["prix_sortie"] == pytest.approx(100.0)