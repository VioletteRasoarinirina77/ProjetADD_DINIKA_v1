"""Tests du service FastAPI (main.py) — utilise TestClient, aucun serveur réel nécessaire."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_repond_ok():
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "ok"
    assert "GOLD" in reponse.json()["instruments_configures"]


def test_obtenir_signal_gold():
    reponse = client.get("/signal/GOLD")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["instrument_id"] == "GOLD"
    assert corps["indicateurs"]["sma_20"] is not None


def test_obtenir_signal_instrument_inconnu_renvoie_404():
    reponse = client.get("/signal/INSTRUMENT_INCONNU")
    assert reponse.status_code == 404


def test_obtenir_backtest_es():
    reponse = client.get("/backtest/ES?taille_train=60&taille_test=20")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert "nb_trades" in corps


def test_obtenir_backtest_avec_fenetres_trop_grandes_renvoie_422():
    """Fenêtres plus grandes que l'historique dispo -> erreur explicite, pas un crash."""
    reponse = client.get("/backtest/GOLD?taille_train=1000&taille_test=1000")
    assert reponse.status_code == 422




