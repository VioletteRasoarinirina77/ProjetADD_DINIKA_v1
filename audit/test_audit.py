"""Tests de audit/logger.py et de son intégration dans main.py."""

import json

from fastapi.testclient import TestClient

from audit.logger import FICHIER_AUDIT, journaliser_decision, journaliser_requete
from main import app

client = TestClient(app)


def _dernieres_lignes_json(n: int) -> list[dict]:
    with open(FICHIER_AUDIT, encoding="utf-8") as f:
        lignes = f.readlines()
    return [json.loads(ligne) for ligne in lignes[-n:]]


def test_journaliser_requete_ecrit_une_ligne_json_valide():
    journaliser_requete("GET", "/health", 200, 12.34)
    derniere = _dernieres_lignes_json(1)[0]

    assert derniere["type"] == "requete_http"
    assert derniere["methode"] == "GET"
    assert derniere["chemin"] == "/health"
    assert derniere["statut_code"] == 200
    assert derniere["duree_ms"] == 12.34
    assert "timestamp" in derniere


def test_journaliser_decision_ecrit_les_champs_fournis():
    journaliser_decision("signal_quantitatif", "GOLD", {"rsi_14": 58.3, "atr_14": 12.4})
    derniere = _dernieres_lignes_json(1)[0]

    assert derniere["type"] == "signal_quantitatif"
    assert derniere["instrument_id"] == "GOLD"
    assert derniere["rsi_14"] == 58.3
    assert derniere["atr_14"] == 12.4


def test_appel_signal_journalise_la_requete_et_la_decision():
    """Test d'intégration : UN appel HTTP doit produire DEUX lignes de journal --
    la requête (middleware) ET la décision (dans la route elle-même)."""
    client.get("/signal/GOLD")
    lignes = _dernieres_lignes_json(2)
    types_presents = {ligne["type"] for ligne in lignes}

    assert "signal_quantitatif" in types_presents
    assert "requete_http" in types_presents


def test_appel_backtest_journalise_les_metriques():
    client.get("/backtest/ES?taille_train=60&taille_test=20")
    lignes = _dernieres_lignes_json(5)
    decisions_backtest = [ligne for ligne in lignes if ligne["type"] == "validation_backtest"]

    assert len(decisions_backtest) >= 1
    assert decisions_backtest[-1]["instrument_id"] == "ES"
    assert "nb_trades" in decisions_backtest[-1]


def test_requete_en_erreur_est_aussi_journalisee():
    """Même un instrument inconnu (404) doit apparaître dans le journal --
    un audit qui ne trace que les succès ne sert à rien en cas d'incident."""
    client.get("/signal/INSTRUMENT_INCONNU")
    derniere_requete = [ligne for ligne in _dernieres_lignes_json(3) if ligne["type"] == "requete_http"]

    assert len(derniere_requete) >= 1
    assert derniere_requete[-1]["statut_code"] == 404


def test_le_fichier_de_log_existe_et_grandit_avec_l_usage():
    taille_avant = FICHIER_AUDIT.stat().st_size
    client.get("/health")
    taille_apres = FICHIER_AUDIT.stat().st_size
    assert taille_apres > taille_avant
