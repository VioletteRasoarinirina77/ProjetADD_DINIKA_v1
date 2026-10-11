
"""Tests de la courbe d'equity D3."""

import numpy as np
import pandas as pd
import pytest

from backtest.equity import courbe_equity


def test_equity_sans_trade_reste_egale_au_capital_initial():
    """Sans trade, le capital reste constant."""
    index = pd.date_range(
        "2026-01-01",
        periods=3,
        freq="D",
        tz="UTC",
    )
    df = pd.DataFrame(
        {"close": [100.0, 105.0, 110.0]},
        index=index,
    )

    equity = courbe_equity(
        df=df,
        trades=[],
        capital_initial=10_000.0,
        multiplicateur_contrat=1.0,
    )

    assert len(equity) == len(df) + 1
    np.testing.assert_array_equal(
        equity,
        [10_000.0, 10_000.0, 10_000.0, 10_000.0],
    )


def test_equity_prend_en_compte_un_trade_cloture():
    """Le PnL latent puis le PnL réalisé sont reflétés dans l'equity."""
    index = pd.date_range(
        "2026-01-01",
        periods=3,
        freq="D",
        tz="UTC",
    )
    df = pd.DataFrame(
        {"close": [100.0, 110.0, 120.0]},
        index=index,
    )
    trades = [
        {
            "entree_ts": index[0],
            "sortie_ts": index[2],
            "prix_entree": 100.0,
            "taille": 1.0,
            "pnl_dollars": 20.0,
        }
    ]

    equity = courbe_equity(
        df=df,
        trades=trades,
        capital_initial=1_000.0,
        multiplicateur_contrat=1.0,
    )

    np.testing.assert_allclose(
        equity,
        [1_000.0, 1_000.0, 1_010.0, 1_020.0],
    )


def test_equity_rejette_un_timestamp_absent_du_dataframe():
    """Un trade doit référencer des bougies présentes dans le DataFrame."""
    index = pd.date_range(
        "2026-01-01",
        periods=2,
        freq="D",
        tz="UTC",
    )
    df = pd.DataFrame(
        {"close": [100.0, 110.0]},
        index=index,
    )
    trades = [
        {
            "entree_ts": pd.Timestamp("2026-01-03", tz="UTC"),
            "sortie_ts": index[1],
            "prix_entree": 100.0,
            "taille": 1.0,
            "pnl_dollars": 10.0,
        }
    ]

    with pytest.raises(KeyError):
        courbe_equity(
            df=df,
            trades=trades,
            capital_initial=1_000.0,
            multiplicateur_contrat=1.0,
        )
