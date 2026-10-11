"""Tests des métriques D3 (`backtest/metrics.py`) : Sharpe journalier annualisé et drawdown sur
equity, en dollars — décision D-009, figée."""

import numpy as np
import pytest

from backtest.metrics import (
    JOURS_TRADING_PAR_AN,
    calculer_drawdown_equity,
    calculer_metriques,
    calculer_sharpe_annualise,
)


def test_jours_trading_par_an_vaut_252():
    assert JOURS_TRADING_PAR_AN == 252


# --------------------------------------------------------------------------- Sharpe


def test_sharpe_nul_si_equity_constante():
    assert calculer_sharpe_annualise(np.array([10_000.0] * 10)) == 0.0


def test_sharpe_nul_si_moins_de_2_rendements():
    assert calculer_sharpe_annualise(np.array([10_000.0])) == 0.0
    assert calculer_sharpe_annualise(np.array([10_000.0, 10_100.0])) == 0.0


def test_sharpe_positif_si_la_tendance_est_haussiere_et_reguliere():
    equity = np.array([10_000.0, 10_100.0, 10_200.0, 10_100.0, 10_300.0, 10_400.0])
    assert calculer_sharpe_annualise(equity) > 0.0


def test_sharpe_valeur_connue_calculee_a_la_main():
    equity = np.array([100.0, 101.0, 99.99, 100.99])
    rendements = equity[1:] / equity[:-1] - 1.0  # rendements journaliers simples
    attendu = rendements.mean() / rendements.std(ddof=1) * np.sqrt(JOURS_TRADING_PAR_AN)
    assert calculer_sharpe_annualise(equity) == pytest.approx(attendu, rel=1e-6)


def test_sharpe_annualise_par_racine_252():
    """Régression du choix D-009 : le facteur d'annualisation est bien racine(252), pas 252 ni 1."""
    equity = np.array([100.0, 101.0, 99.5, 100.8, 99.9, 101.2])
    rendements = equity[1:] / equity[:-1] - 1.0
    sharpe_journalier = rendements.mean() / rendements.std(ddof=1)
    assert calculer_sharpe_annualise(equity) == pytest.approx(sharpe_journalier * np.sqrt(252), rel=1e-6)


# --------------------------------------------------------------------------- Drawdown


def test_drawdown_nul_si_equity_toujours_croissante():
    assert calculer_drawdown_equity(np.array([100.0, 110.0, 120.0])) == 0.0


def test_drawdown_valeur_connue_calculee_a_la_main():
    # 100 -> 110 (sommet) -> 88 : drawdown = (110 - 88) / 110 = 0,20.
    assert calculer_drawdown_equity(np.array([100.0, 110.0, 88.0])) == pytest.approx(0.20)


def test_drawdown_ne_depend_pas_de_la_valeur_absolue_du_capital():
    """Ratio sans unité : multiplier toute l'equity par 200 ne change pas le résultat (D-012 :
    le capital ES est 200x celui de GOLD, ce n'est pas ce qui doit faire varier le drawdown)."""
    base = np.array([100.0, 90.0, 95.0, 80.0, 105.0])
    assert calculer_drawdown_equity(base * 200) == pytest.approx(calculer_drawdown_equity(base))


def test_drawdown_toujours_borne_entre_0_et_1():
    equity = np.array([100.0, 50.0, 10.0, 5.0, 1.0])
    dd = calculer_drawdown_equity(equity)
    assert 0.0 <= dd <= 1.0


def test_drawdown_refuse_une_equity_vide():
    with pytest.raises(ValueError, match="sans equity"):
        calculer_drawdown_equity(np.array([]))


def test_drawdown_refuse_un_sommet_non_positif():
    with pytest.raises(ValueError, match="strictement positive"):
        calculer_drawdown_equity(np.array([-10.0, -5.0]))


# --------------------------------------------------------------------------- calculer_metriques


def test_metriques_sans_trade_renvoient_des_valeurs_absentes_et_zero_trade():
    m = calculer_metriques([])
    assert (m.sharpe, m.drawdown_max, m.taux_reussite, m.nb_trades) == (None, None, None, 0)


def test_metriques_exige_une_courbe_d_equity_des_qu_il_y_a_des_trades():
    """Régression : avant D-009, le Sharpe/drawdown se calculaient sur le seul PnL en points, sans
    lien avec le capital ni la taille réellement dimensionnée par D4 — non représentatif du compte."""
    with pytest.raises(ValueError, match="courbe d'equity"):
        calculer_metriques([{"pnl_points": 10.0}])


def test_metriques_taux_de_reussite_porte_sur_le_pnl_en_points_pas_sur_l_equity():
    trades = [{"pnl_points": 10.0}, {"pnl_points": -5.0}, {"pnl_points": 20.0}, {"pnl_points": -5.0}]
    equity = np.array([10_000.0, 10_100.0, 10_050.0, 10_250.0, 10_200.0])
    m = calculer_metriques(trades, equity)
    assert m.nb_trades == 4
    assert m.taux_reussite == 0.5
    assert m.sharpe == round(calculer_sharpe_annualise(equity), 3)
    assert m.drawdown_max == round(calculer_drawdown_equity(equity), 4)
