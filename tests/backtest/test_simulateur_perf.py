"""Garde-fou de l'optimisation de simuler_trades (lecture en tableaux numpy).

La version rapide doit produire EXACTEMENT les mêmes trades que la version de référence, lente mais
lisible, écrite ci-dessous ligne par ligne (accès `df.iloc[i]`) : mêmes timestamps, mêmes prix, mêmes
tailles, mêmes PnL. L'optimisation répond au critère CDC D7 (synthèse < 3 s) : l'accès ligne par ligne
représentait ~94 % du temps d'un backtest.
"""

from pathlib import Path

import pandas as pd
import pytest

from backtest.simulator import simuler_trades
from backtest.walk_forward import decouper_walk_forward
from config.instruments import obtenir_config, resoudre_capital_virtuel
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from integration.pack_repository import PackDataRepository
from risk.position_sizing import calculer_risque
from strategy.rules import ajouter_signaux

PACK = Path(__file__).parents[2] / "fixtures" / "integration" / "pack_es_v1"


def _simuler_trades_reference(df, instrument_id, capital, k):
    """Version de référence (accès ligne par ligne) : mêmes règles que simuler_trades."""
    config = obtenir_config(instrument_id)
    capital_courant = resoudre_capital_virtuel(instrument_id, capital)
    trades, position = [], None
    for i in range(len(df) - 1):
        ligne, suivante = df.iloc[i], df.iloc[i + 1]
        if position is None:
            if bool(ligne["signal_entree"]) and not pd.isna(ligne["atr_14"]):
                prix = float(suivante["open"])
                risque = calculer_risque(
                    prix, float(ligne["atr_14"]), instrument_id, capital_courant,
                    multiplicateur_atr_stop_override=k,
                )
                position = (prix, df.index[i + 1], risque.stop_loss, risque.take_profit,
                            risque.taille_position_recommandee)
            continue
        prix, entree_ts, stop, objectif, taille = position
        touche_stop, touche_tp = suivante["low"] <= stop, suivante["high"] >= objectif
        if touche_stop or touche_tp:
            sortie = min(stop, float(suivante["open"])) if touche_stop else objectif
            points = sortie - prix - config.spread_points
            dollars = points * config.multiplicateur_contrat * taille
            capital_courant += dollars
            trades.append({
                "entree_ts": entree_ts, "sortie_ts": df.index[i + 1], "prix_entree": prix,
                "prix_sortie": sortie, "pnl_points": points, "taille": taille, "pnl_dollars": dollars,
            })
            position = None
    return trades


@pytest.fixture(scope="module")
def donnees_es():
    bougies = PackDataRepository(PACK).candles_validees("ES")[:1500]
    return ajouter_signaux(ajouter_indicateurs(bougies_vers_dataframe(bougies), "ES"))


@pytest.mark.parametrize("k", [None, 1.5, 3.0])
def test_la_version_rapide_reproduit_exactement_la_reference_sur_la_serie(donnees_es, k):
    capital = 2_000_000.0
    assert simuler_trades(donnees_es, "ES", capital, k) == _simuler_trades_reference(
        donnees_es, "ES", capital, k
    )


def test_la_version_rapide_reproduit_la_reference_sur_chaque_fenetre_train_et_test(donnees_es):
    fenetres = decouper_walk_forward(donnees_es, 250, 60)
    assert fenetres
    for train, test in fenetres[:8]:
        for tranche in (train, test):
            assert simuler_trades(tranche, "ES", 2_000_000.0, 2.0) == _simuler_trades_reference(
                tranche, "ES", 2_000_000.0, 2.0
            )