"""Tests de la route POST /reconciliation (main.py)."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _bougie(source: str, close: float) -> dict:
    return {
        "instrument_id": "GOLD", "source": source, "timeframe": "1h",
        "timestamp": "2026-01-01T10:00:00Z",
        "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 100,
    }


def test_ecart_important_est_detecte_via_l_api():
    reponse = client.post(
        "/reconciliation",
        json={"bougies_source_a": [_bougie("COMEX", 2400.0)], "bougies_source_b": [_bougie("OANDA", 2450.0)]},
        params={"tolerance_pct": 0.5},
    )
    assert reponse.status_code == 200
    anomalies = reponse.json()
    assert len(anomalies) == 1
    assert anomalies[0]["source_a"] == "COMEX"
    assert anomalies[0]["source_b"] == "OANDA"


def test_ecart_faible_ne_produit_aucune_anomalie_via_l_api():
    reponse = client.post(
        "/reconciliation",
        json={"bougies_source_a": [_bougie("COMEX", 2400.0)], "bougies_source_b": [_bougie("OANDA", 2402.0)]},
        params={"tolerance_pct": 0.5},
    )
    assert reponse.status_code == 200
    assert reponse.json() == []


def test_reconciliation_avec_listes_vides_ne_plante_pas():
    reponse = client.post("/reconciliation", json={"bougies_source_a": [], "bougies_source_b": []})
    assert reponse.status_code == 200
    assert reponse.json() == []


def test_reconciliation_refuse_un_corps_de_requete_invalide():
    reponse = client.post("/reconciliation", json={"bougies_source_a": []})  # source_b manquante
    assert reponse.status_code == 422
