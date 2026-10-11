"""Tests de paper_trading/portfolio.py (exposition maximale au niveau portefeuille)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from config.instruments import obtenir_config
from contracts.schemas import Bougie
from main import app
from paper_trading.portfolio import simuler_portefeuille

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def charger_bougies(nom_fichier: str) -> list[Bougie]:
    with open(FIXTURES_DIR / nom_fichier) as f:
        donnees = json.load(f)
    return [Bougie(**d) for d in donnees]




def _serie_qui_monte(
    instrument_id: str,
    source: str,
    prix_depart: float,
    n: int = 40,
) -> list[Bougie]:
    """Crée une série stable avec un vrai croisement haussier SMA20."""

    bougies = []

    timeframe = "1h" if instrument_id == "GOLD" else "1D"

    for i in range(n):
        if i < 19:
            close = prix_depart - 0.10
        elif i == 19:
            close = prix_depart - 0.20
        elif i == 20:
            close = prix_depart + 0.20
        else:
            close = prix_depart + 0.20 + (i - 20) * 0.05

        bougies.append(
            Bougie(
                instrument_id=instrument_id,
                source=source,
                timestamp=datetime(
                    2026,
                    1,
                    1,
                    tzinfo=UTC,
                ) + timedelta(hours=i),
                timeframe=timeframe,
                open=close - 0.02,
                high=close + 0.20,
                low=close - 0.20,
                close=close,
                volume=1000.0,
                open_interest=None,
            )
        )

    return bougies



client = TestClient(app)


def test_portefeuille_gold_es_repond_200():
    reponse = client.get(
        "/portefeuille?instruments=GOLD,ES&plafond_exposition_ratio=3.0"
    )

    assert reponse.status_code == 200

    corps = reponse.json()

    assert "trades" in corps
    assert "trades_rejetes" in corps
    # D-012 : capital partagé du portefeuille = le plus grand capital_virtuel_defaut demandé (ES).
    assert corps["capital_initial"] == obtenir_config("ES").capital_virtuel_defaut


def test_portefeuille_avec_instrument_inconnu_renvoie_404():
    reponse = client.get(
        "/portefeuille?instruments=GOLD,BITCOIN"
    )

    assert reponse.status_code == 404


def test_portefeuille_avec_plafond_bas_produit_plus_de_rejets():
    reponse_large = client.get(
        "/portefeuille"
        "?instruments=GOLD,ES"
        "&plafond_exposition_ratio=1000000"
    )

    reponse_stricte = client.get(
        "/portefeuille"
        "?instruments=GOLD,ES"
        "&plafond_exposition_ratio=0.001"
    )

    assert len(reponse_large.json()["trades_rejetes"]) == 0

    assert len(
        reponse_stricte.json()["trades_rejetes"]
    ) >= len(
        reponse_large.json()["trades_rejetes"]
    )


def test_portefeuille_un_seul_instrument_fonctionne_aussi():
    reponse = client.get(
        "/portefeuille?instruments=GOLD"
    )

    assert reponse.status_code == 200
    assert reponse.json()["trades_rejetes"] == []


def test_portefeuille_capital_initial_invalide():
    reponse = client.get(
        "/portefeuille"
        "?instruments=GOLD"
        "&capital_initial=0"
    )

    assert reponse.status_code in (400, 422, 500)


def test_portefeuille_plafond_invalide():
    reponse = client.get(
        "/portefeuille"
        "?instruments=GOLD"
        "&plafond_exposition_ratio=0"
    )

    assert reponse.status_code in (400, 422, 500)





def test_avec_un_plafond_tres_bas_presque_tout_est_rejete():
    """Plafond quasi nul -> dès qu'une position est ouverte, plus rien d'autre ne peut l'être."""
    bougies = {
        "GOLD": _serie_qui_monte("GOLD", "COMEX", 2400.0),
        "ES": _serie_qui_monte("ES", "CME", 5800.0),
    }
    resultat = simuler_portefeuille(bougies, capital_initial=10_000.0, plafond_exposition_ratio=0.001)

    # Avec un plafond aussi bas, AUCUNE position ne devrait même pouvoir s'ouvrir
    assert len(resultat.trades) == 0
    assert len(resultat.trades_rejetes) >= 1


def test_avec_un_plafond_enorme_rien_n_est_rejete():
    """Plafond très large -> équivalent à l'absence de plafond, aucun rejet."""
    bougies = {
        "GOLD": _serie_qui_monte("GOLD", "COMEX", 2400.0),
        "ES": _serie_qui_monte("ES", "CME", 5800.0),
    }
    resultat = simuler_portefeuille(bougies, capital_initial=10_000.0, plafond_exposition_ratio=1_000_000.0)

    assert resultat.trades_rejetes == []


def test_trade_rejete_porte_bien_l_instrument_et_le_plafond_concernes():
    bougies = {
        "GOLD": _serie_qui_monte("GOLD", "COMEX", 2400.0),
        "ES": _serie_qui_monte("ES", "CME", 5800.0),
    }
    resultat = simuler_portefeuille(bougies, capital_initial=10_000.0, plafond_exposition_ratio=0.001)

    rejet = resultat.trades_rejetes[0]
    assert rejet.instrument_id in {"GOLD", "ES"}
    assert rejet.exposition_demandee > rejet.plafond - rejet.exposition_deja_engagee


def test_exposition_deja_engagee_augmente_avec_une_position_ouverte():
    """Le 2e rejet (si l'instrument A a déjà une position ouverte) doit montrer une
    exposition déjà engagée strictement positive -- preuve que le portefeuille est
    bien pris en compte, pas juste chaque instrument isolément."""
    bougies = {
        "GOLD": _serie_qui_monte("GOLD", "COMEX", 2400.0),
        "ES": _serie_qui_monte("ES", "CME", 5800.0),
    }
    resultat = simuler_portefeuille(bougies, capital_initial=10_000.0, plafond_exposition_ratio=30.0)

    expositions_engagees = [r.exposition_deja_engagee for r in resultat.trades_rejetes]
    assert any(e > 0 for e in expositions_engagees)


def test_fonctionne_sur_les_fixtures_reelles_gold_et_es():
    """Test d'intégration de bout en bout, sans hypothèse sur le nombre exact de trades
    (données semi-aléatoires) -- juste la cohérence générale du résultat."""
    bougies = {
        "GOLD": charger_bougies("backtest/bougies_gold_300h.json"),
        "ES": charger_bougies("backtest/bougies_es_300h.json"),
    }
    resultat = simuler_portefeuille(bougies, capital_initial=10_000.0, plafond_exposition_ratio=30.0)

    assert resultat.capital_initial == 10_000.0
    assert isinstance(resultat.capital_final, float)
    assert len(resultat.courbe_capital) == len(resultat.trades) + 1
    # Le plafond doit avoir un effet mesurable par rapport à l'absence de plafond
    resultat_sans_plafond = simuler_portefeuille(
        bougies, capital_initial=10_000.0, plafond_exposition_ratio=1_000_000.0
    )
    assert len(resultat_sans_plafond.trades_rejetes) == 0
    assert len(resultat.trades) <= len(resultat_sans_plafond.trades)


def test_un_seul_instrument_se_comporte_normalement():
    """Avec un seul instrument, aucune concurrence possible -> aucun rejet."""
    bougies = {"GOLD": _serie_qui_monte("GOLD", "COMEX", 2400.0)}
    resultat = simuler_portefeuille(bougies, capital_initial=10_000.0, plafond_exposition_ratio=30.0)
    assert resultat.trades_rejetes == []


def test_simuler_portefeuille_sans_aucun_instrument_renvoie_le_capital_inchange():
    """Cas limite (A6) : un dict vide ne doit pas planter -- il ne se produit qu'avec un mauvais
    appel côté API/panneau, mais le comportement doit rester défini."""
    resultat = simuler_portefeuille({}, capital_initial=5_000.0)
    assert resultat.capital_final == 5_000.0
    assert resultat.trades == []
    assert resultat.trades_rejetes == []
    assert resultat.courbe_capital == [5_000.0]
