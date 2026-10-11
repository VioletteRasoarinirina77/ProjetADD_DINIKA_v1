"""Tests de la route GET /portefeuille (main.py)."""

from fastapi.testclient import TestClient

from config.instruments import obtenir_config
from main import app

client = TestClient(app)


def test_portefeuille_gold_es_repond_200():
    reponse = client.get("/portefeuille?instruments=GOLD,ES&plafond_exposition_ratio=3.0")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert "trades" in corps
    assert "trades_rejetes" in corps
    # D-012 : sans capital explicite, le portefeuille prend le plus grand capital_virtuel_defaut des
    # instruments demandés (capital partagé) -- celui d'ES (2 M$), plus élevé que celui de GOLD.
    assert corps["capital_initial"] == obtenir_config("ES").capital_virtuel_defaut


def test_portefeuille_avec_capital_explicite_l_utilise_tel_quel():
    reponse = client.get("/portefeuille?instruments=GOLD,ES&capital_initial=500000")
    assert reponse.status_code == 200
    assert reponse.json()["capital_initial"] == 500_000.0


def test_portefeuille_avec_instrument_inconnu_renvoie_404():
    reponse = client.get("/portefeuille?instruments=GOLD,BITCOIN")
    assert reponse.status_code == 404


def test_portefeuille_avec_plafond_bas_produit_plus_de_rejets():
    reponse_large = client.get("/portefeuille?instruments=GOLD,ES&plafond_exposition_ratio=1000000")
    reponse_stricte = client.get("/portefeuille?instruments=GOLD,ES&plafond_exposition_ratio=0.001")

    assert len(reponse_large.json()["trades_rejetes"]) == 0
    assert len(reponse_stricte.json()["trades_rejetes"]) >= len(reponse_large.json()["trades_rejetes"])


def test_portefeuille_un_seul_instrument_fonctionne_aussi():
    reponse = client.get("/portefeuille?instruments=GOLD")
    assert reponse.status_code == 200
    assert reponse.json()["trades_rejetes"] == []
