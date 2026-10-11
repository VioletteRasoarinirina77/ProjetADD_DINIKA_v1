"""Tests des SORTIES de paper_trading/portfolio.py (stop-loss / take-profit).

Ces branches portent le calcul du PnL en dollars et de la courbe de capital du
portefeuille (D8) : elles ne doivent jamais rester sans test.
"""

from datetime import UTC, datetime, timedelta

import pytest

from config.instruments import obtenir_config
from contracts.schemas import Bougie
from paper_trading.portfolio import simuler_portefeuille

PRIX_DEPART = 5000.0
CAPITAL = 100_000.0


def _serie_es(derniere_bougie, n: int = 40) -> list[Bougie]:
    """Série ES quotidienne avec un croisement haussier net (entrée LONG), puis
    3 bougies finales dont on contrôle exactement (close, high, low).

    `derniere_bougie(close)` retourne le triplet (close, high, low) des 3
    dernières bougies -- ce qui déclenche take-profit, stop-loss ou les deux.
    """
    bougies = []
    for i in range(n):
        if i < 19:
            close = PRIX_DEPART - 1
        elif i == 19:
            close = PRIX_DEPART - 2
        elif i == 20:
            close = PRIX_DEPART + 2
        else:
            close = PRIX_DEPART + 2 + (i - 20) * 0.5
        haut, bas = close + 2, close - 2
        if i >= n - 3:
            close, haut, bas = derniere_bougie(close)
        bougies.append(
            Bougie(
                instrument_id="ES",
                source="databento",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
                timeframe="1D",
                open=close,
                high=max(haut, close),
                low=min(bas, close),
                close=close,
                volume=1000.0,
                open_interest=None,
            )
        )
    return bougies


def _simuler(derniere_bougie):
    return simuler_portefeuille({"ES": _serie_es(derniere_bougie)}, capital_initial=CAPITAL)


def test_un_take_profit_touche_ferme_le_trade_avec_un_gain():
    resultat = _simuler(lambda c: (c + 500, c + 500, c))

    assert len(resultat.trades) == 1
    trade = resultat.trades[0]
    assert trade.prix_sortie > trade.prix_entree
    assert trade.pnl_dollars > 0
    assert resultat.capital_final > CAPITAL


def test_un_stop_loss_touche_ferme_le_trade_avec_une_perte():
    resultat = _simuler(lambda c: (c - 500, c, c - 500))

    assert len(resultat.trades) == 1
    trade = resultat.trades[0]
    assert trade.prix_sortie < trade.prix_entree
    assert trade.pnl_dollars < 0
    assert resultat.capital_final < CAPITAL


def test_si_stop_et_profit_sont_touches_dans_la_meme_bougie_le_stop_est_prioritaire():
    """Convention conservatrice documentée : on ne suppose jamais le meilleur cas."""
    resultat = _simuler(lambda c: (c, c + 500, c - 500))

    assert len(resultat.trades) == 1
    trade = resultat.trades[0]
    assert trade.prix_sortie < trade.prix_entree
    assert trade.pnl_dollars < 0


def test_le_pnl_du_trade_est_coherent_avec_multiplicateur_taille_et_spread():
    """PnL = (sortie - entrée - spread) * multiplicateur * taille (entière)."""
    config = obtenir_config("ES")
    resultat = _simuler(lambda c: (c + 500, c + 500, c))
    trade = resultat.trades[0]

    attendu = (
        (trade.prix_sortie - trade.prix_entree - config.spread_points)
        * config.multiplicateur_contrat
        * trade.taille_position
    )
    assert trade.pnl_dollars == pytest.approx(attendu, abs=0.01)
    assert trade.taille_position == int(trade.taille_position)  # entier de contrats


def test_la_courbe_de_capital_suit_les_trades_fermes():
    resultat = _simuler(lambda c: (c + 500, c + 500, c))

    assert resultat.courbe_capital[0] == CAPITAL
    assert resultat.courbe_capital[-1] == pytest.approx(resultat.capital_final, abs=0.01)
    assert len(resultat.courbe_capital) == len(resultat.trades) + 1
