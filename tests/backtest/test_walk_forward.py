"""
Tests de backtest/walk_forward.py.

Les scénarios sont construits de manière déterministe afin de vérifier
précisément les règles du backtesting walk-forward D3.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from backtest.walk_forward import (
    calculer_metriques,
    decouper_walk_forward,
    generer_signaux_entree,
    simuler_trades,
    walk_forward_backtest,
)
from contracts.schemas import Bougie

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"


def charger_bougies_gold_150h() -> list[Bougie]:
    chemin = (
        FIXTURES_DIR
        / "backtest"
        / "bougies_gold_150h.json"
    )

    with open(chemin, encoding="utf-8") as fichier:
        donnees = json.load(fichier)

    return [
        Bougie.model_validate(item)
        for item in donnees
    ]


def test_decouper_walk_forward_nombre_et_tailles_de_fenetres():
    df = pd.DataFrame({
        "x": range(100)
    })

    fenetres = decouper_walk_forward(
        df,
        taille_train=60,
        taille_test=20,
    )

    # Fenêtres :
    # 0-60 train / 60-80 test
    # 20-80 train / 80-100 test
    assert len(fenetres) == 2

    for train, test in fenetres:
        assert len(train) == 60
        assert len(test) == 20


def test_decouper_walk_forward_vide_si_pas_assez_de_donnees():
    df = pd.DataFrame({
        "x": range(50)
    })

    assert (
        decouper_walk_forward(
            df,
            taille_train=60,
            taille_test=20,
        )
        == []
    )


def test_generer_signaux_entree_ne_s_active_qu_au_croisement():
    """
    Le signal doit apparaître uniquement au croisement haussier.
    """
    df = pd.DataFrame({
        "close": [100, 105, 95, 90, 120],
        "sma_20": [102, 102, 102, 102, 102],
    })

    signaux = generer_signaux_entree(df)

    assert list(signaux) == [
        False,
        True,
        False,
        False,
        True,
    ]


def test_simuler_trades_stop_loss_touche():
    """
    Scénario :
        entrée = 110
        ATR = 5
        multiplicateur GOLD = 2
        stop = 100
        take-profit = 130

    La bougie suivante touche le stop.
    """
    df = pd.DataFrame(
        {
            "open": [104, 110, 111, 101],
            "high": [106, 112, 115, 103],
            "low": [103, 108, 99, 100],
            "close": [105, 111, 101, 102],
            "sma_20": [102, 102, 102, 102],
            "atr_14": [5.0, 5.0, 5.0, 5.0],
        },
        index=pd.date_range(
            "2026-01-01",
            periods=4,
            freq="h",
            tz="UTC",
        ),
    )

    trades = simuler_trades(
        df,
        "GOLD",
    )

    assert len(trades) == 1

    trade = trades[0]

    assert trade["prix_entree"] == 110.0

    assert (
        trade["entree_ts"]
        == df.index[1]
    )

    assert (
        trade["prix_sortie"]
        == pytest.approx(100.0)
    )

    assert trade["pnl_points"] < 0


def test_calculer_metriques_sans_trade():
    metriques = calculer_metriques([])

    assert metriques.nb_trades == 0
    assert metriques.sharpe is None
    assert metriques.taux_reussite is None
    assert metriques.drawdown_max is None


def test_walk_forward_rejette_taille_train_invalide():
    bougies = charger_bougies_gold_150h()

    with pytest.raises(
        ValueError,
        match="taille_train",
    ):
        walk_forward_backtest(
            bougies,
            "GOLD",
            taille_train=0,
            taille_test=20,
        )


def test_walk_forward_rejette_taille_test_invalide():
    bougies = charger_bougies_gold_150h()

    with pytest.raises(
        ValueError,
        match="taille_test",
    ):
        walk_forward_backtest(
            bougies,
            "GOLD",
            taille_train=60,
            taille_test=0,
        )


def test_walk_forward_rejette_capital_invalide():
    bougies = charger_bougies_gold_150h()

    with pytest.raises(
        ValueError,
        match="capital_virtuel",
    ):
        walk_forward_backtest(
            bougies,
            "GOLD",
            taille_train=60,
            taille_test=20,
            capital_virtuel=0,
        )


def test_walk_forward_backtest_leve_erreur_si_pas_assez_de_bougies():
    chemin = (
        FIXTURES_DIR
        / "indicators"
        / "bougies_gold_30h.json"
    )


    with open(
        chemin,
        encoding="utf-8",
    ) as fichier:
        donnees = json.load(fichier)

    bougies = [
        Bougie(**donnee)
        for donnee in donnees
    ]

    with pytest.raises(
        ValueError,
        match="Pas assez de bougies",
    ):
        walk_forward_backtest(
            bougies,
            "GOLD",
            taille_train=60,
            taille_test=20,
        )


def test_walk_forward_backtest_sur_fixture_reelle():
    """
    Test d'intégration de bout en bout.

    Le test vérifie la cohérence des métriques sans imposer une
    performance particulière à la stratégie.
    """
    bougies = charger_bougies_gold_150h()

    resultat = walk_forward_backtest(
        bougies,
        "GOLD",
        taille_train=60,
        taille_test=20,
    )

    assert resultat.nb_trades is not None

    if resultat.nb_trades > 0:
        assert (
            0.0
            <= resultat.taux_reussite
            <= 1.0
        )

        assert (
            resultat.drawdown_max
            >= 0.0
        )


def test_walk_forward_backtest_est_deterministe():
    """
    Deux exécutions avec les mêmes données et paramètres doivent
    produire exactement les mêmes métriques.
    """
    bougies = charger_bougies_gold_150h()

    resultat_1 = walk_forward_backtest(
        bougies,
        "GOLD",
        taille_train=60,
        taille_test=20,
    )

    resultat_2 = walk_forward_backtest(
        bougies,
        "GOLD",
        taille_train=60,
        taille_test=20,
    )

    assert (
        resultat_1.model_dump()
        == resultat_2.model_dump()
    )
