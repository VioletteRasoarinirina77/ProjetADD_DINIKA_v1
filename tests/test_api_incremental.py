"""Tests du branchement incrémental dans main.py (état persistant par instrument).

Complète tests/test_main.py (déjà existant) en vérifiant spécifiquement le
COMPORTEMENT temps réel : chauffage une seule fois, cache réutilisé ensuite,
et mise à jour correcte via l'ingestion d'une nouvelle bougie.
"""

from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)


def _reinitialiser_cache():
    """Les caches sont des dict au niveau module -- on les vide entre les tests
    pour ne pas dépendre de l'ordre d'exécution des autres fichiers de tests."""
    main._etats_indicateurs.clear()
    main._dernier_signal.clear()


def test_le_premier_appel_chauffe_le_cache():
    _reinitialiser_cache()
    assert "GOLD" not in main._etats_indicateurs

    reponse = client.get("/signal/GOLD")

    assert reponse.status_code == 200
    assert "GOLD" in main._etats_indicateurs
    assert "GOLD" in main._dernier_signal


def test_le_deuxieme_appel_reutilise_le_cache_sans_le_recalculer():
    _reinitialiser_cache()
    client.get("/signal/GOLD")
    etat_apres_premier_appel = main._etats_indicateurs["GOLD"]

    client.get("/signal/GOLD")
    etat_apres_second_appel = main._etats_indicateurs["GOLD"]

    # Même nombre de bougies vues -> le 2e GET n'a pas rechauffé l'historique
    assert etat_apres_premier_appel.nb_bougies_vues == etat_apres_second_appel.nb_bougies_vues


def test_ingerer_bougie_augmente_le_nombre_de_bougies_vues_de_exactement_un():
    """LE test qui prouve le coût constant : une bougie ingérée = +1, jamais plus."""
    _reinitialiser_cache()
    client.get("/signal/GOLD")  # chauffe le cache
    nb_avant = main._etats_indicateurs["GOLD"].nb_bougies_vues

    nouvelle_bougie = {
        "instrument_id": "GOLD", "source": "COMEX", "timeframe": "1h",
        "timestamp": "2026-08-31T00:00:00Z",
        "open": 2270.0, "high": 2280.0, "low": 2265.0, "close": 2278.5, "volume": 1500,
    }
    reponse = client.post("/bougie/GOLD", json=nouvelle_bougie)

    assert reponse.status_code == 200
    assert main._etats_indicateurs["GOLD"].nb_bougies_vues == nb_avant + 1


def test_ingerer_bougie_met_a_jour_le_signal_renvoye_par_get_signal():
    """Après ingestion, un nouveau GET /signal doit refléter la nouvelle bougie,
    pas l'ancienne -- preuve que le cache est bien mis à jour, pas figé."""
    _reinitialiser_cache()
    client.get("/signal/GOLD")

    nouvelle_bougie = {
        "instrument_id": "GOLD", "source": "COMEX", "timeframe": "1h",
        "timestamp": "2026-08-31T00:00:00Z",
        "open": 2270.0, "high": 2280.0, "low": 2265.0, "close": 2278.5, "volume": 1500,
    }
    client.post("/bougie/GOLD", json=nouvelle_bougie)

    signal_apres = client.get("/signal/GOLD").json()
    assert signal_apres["timestamp"] == "2026-08-31T00:00:00Z"


def test_ingerer_bougie_refuse_un_instrument_incoherent():
    """Le chemin dit GOLD, le corps dit ES -> doit être rejeté, pas silencieusement ignoré."""
    _reinitialiser_cache()
    bougie_es = {
        "instrument_id": "ES", "source": "CME", "timeframe": "1h",
        "timestamp": "2026-08-31T00:00:00Z",
        "open": 5700.0, "high": 5720.0, "low": 5690.0, "close": 5710.0, "volume": 800,
    }
    reponse = client.post("/bougie/GOLD", json=bougie_es)
    assert reponse.status_code == 422


def test_ingerer_bougie_sur_instrument_inconnu_renvoie_404():
    _reinitialiser_cache()
    bougie = {
        "instrument_id": "BITCOIN", "source": "BINANCE", "timeframe": "1h",
        "timestamp": "2026-08-31T00:00:00Z",
        "open": 60000.0, "high": 61000.0, "low": 59500.0, "close": 60500.0, "volume": 10,
    }
    reponse = client.post("/bougie/BITCOIN", json=bougie)
    assert reponse.status_code == 404
