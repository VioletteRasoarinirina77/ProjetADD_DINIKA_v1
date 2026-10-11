"""Tests des branches d'erreur de main.py (A6) : chaque cas défensif ou de repli doit être
exercé au moins une fois, pas seulement le chemin "tout va bien" déjà couvert ailleurs."""


import httpx
import pytest
import respx
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _etat_incremental_propre():
    """Isole chaque test : l'état incrémental (mémoire) ne doit pas fuiter d'un test à l'autre."""
    main._etats_indicateurs.clear()
    main._dernier_signal.clear()
    yield
    main._etats_indicateurs.clear()
    main._dernier_signal.clear()


# --------------------------------------------------------------------- obtenir_bougies_depuis_fixtures


def test_fixture_absente_pour_un_instrument_leve_404():
    """Garde-fou : un instrument du registre sans entrée dans FIXTURES_PAR_INSTRUMENT (oubli lors de
    l'ajout d'un instrument) doit échouer explicitement, jamais silencieusement."""
    with pytest.raises(HTTPException) as exc_info:
        main.obtenir_bougies_depuis_fixtures("INEXISTANT")
    assert exc_info.value.status_code == 404


def test_fichier_de_fixture_manquant_sur_disque_leve_404(monkeypatch):
    monkeypatch.setitem(main.FIXTURES_PAR_INSTRUMENT, "GOLD", "chemin/qui/nexiste/pas.json")
    with pytest.raises(HTTPException) as exc_info:
        main.obtenir_bougies_depuis_fixtures("GOLD")
    assert exc_info.value.status_code == 404
    assert "introuvable" in exc_info.value.detail


def test_fixture_json_corrompue_leve_500(tmp_path, monkeypatch):
    fichier_corrompu = tmp_path / "corrompu.json"
    fichier_corrompu.write_text("{ceci n'est pas du JSON valide", encoding="utf-8")
    monkeypatch.setattr(main, "FIXTURES_DIR", tmp_path)
    monkeypatch.setitem(main.FIXTURES_PAR_INSTRUMENT, "GOLD", "corrompu.json")
    with pytest.raises(HTTPException) as exc_info:
        main.obtenir_bougies_depuis_fixtures("GOLD")
    assert exc_info.value.status_code == 500
    assert "invalide" in exc_info.value.detail


# --------------------------------------------------------------------- obtenir_bougies_via_api


@respx.mock
def test_panne_reseau_vers_la_piste_data_leve_503(monkeypatch):
    """Toute erreur imprévue (timeout, DNS, ...) devient un 503 explicite, jamais une 500 opaque."""
    monkeypatch.setenv("PISTE_DATA_API_URL", "http://127.0.0.1:8000")
    respx.get("http://127.0.0.1:8000/health").mock(side_effect=httpx.ConnectError("connexion refusée"))
    with pytest.raises(HTTPException) as exc_info:
        main.obtenir_bougies_via_api("ES")
    assert exc_info.value.status_code == 503
    assert "indisponible" in exc_info.value.detail


# --------------------------------------------------------------------- obtenir_bougies (dispatcher)


@respx.mock
def test_obtenir_bougies_route_vers_l_api_en_mode_prod(monkeypatch):
    """ENVIRONMENT=prod doit passer par obtenir_bougies_via_api (D2/D3/D4 ne changent pas)."""
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("PISTE_DATA_API_URL", "http://127.0.0.1:8000")
    respx.get("http://127.0.0.1:8000/health").mock(return_value=httpx.Response(200, json={"statut": "ok"}))
    respx.get("http://127.0.0.1:8000/api/v1/instruments/ES/quality").mock(
        return_value=httpx.Response(200, json={"valid": True, "errors": []})
    )
    respx.get("http://127.0.0.1:8000/api/v1/instruments/ES/gaps").mock(
        return_value=httpx.Response(200, json={"has_gaps": False, "gap_count": 0, "gaps": [], "error": None})
    )
    respx.get("http://127.0.0.1:8000/api/v1/instruments/ES/candles").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "instrument_id": "ES",
                    "source": "databento",
                    "timeframe": "1D",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "open": 6500.0,
                    "high": 6510.0,
                    "low": 6490.0,
                    "close": 6505.0,
                    "volume": 1000,
                }
            ],
        )
    )
    bougies = main.obtenir_bougies("ES")
    assert len(bougies) == 1
    assert respx.calls.call_count == 4


# --------------------------------------------------------------------- _etat_ou_chauffer


def test_aucune_bougie_disponible_leve_une_valeur_explicite(monkeypatch):
    monkeypatch.setattr(main, "obtenir_bougies", lambda instrument_id: [])
    with pytest.raises(ValueError, match="Aucune bougie disponible"):
        main._etat_ou_chauffer("GOLD")


def test_indicateurs_jamais_calcules_est_un_garde_fou_defensif(monkeypatch):
    """Cas normalement impossible (mettre_a_jour renvoie toujours des indicateurs) : gardé en test
    pour que ce garde-fou explicite ne se transforme jamais silencieusement en AttributeError."""
    monkeypatch.setattr(main, "mettre_a_jour", lambda etat, bougie: (etat, None))
    with pytest.raises(ValueError, match="Impossible de calculer les indicateurs"):
        main._etat_ou_chauffer("GOLD")


# --------------------------------------------------------------------- /signal et /bougie : propagation


def test_signal_propage_l_erreur_de_chargement_des_donnees(monkeypatch):
    """Une HTTPException levée pendant le chauffage (ex. fixture manquante) doit ressortir telle
    quelle sur /signal, pas être masquée par le except générique."""
    monkeypatch.setitem(main.FIXTURES_PAR_INSTRUMENT, "GOLD", "chemin/absent.json")
    reponse = client.get("/signal/GOLD")
    assert reponse.status_code == 404


def test_signal_transforme_une_valeur_invalide_en_422(monkeypatch):
    monkeypatch.setattr(main, "obtenir_bougies", lambda instrument_id: [])
    reponse = client.get("/signal/GOLD")
    assert reponse.status_code == 422
    assert "Aucune bougie disponible" in reponse.json()["detail"]


def test_bougie_propage_l_erreur_de_chargement_des_donnees(monkeypatch):
    monkeypatch.setitem(main.FIXTURES_PAR_INSTRUMENT, "GOLD", "chemin/absent.json")
    reponse = client.post(
        "/bougie/GOLD",
        json={
            "instrument_id": "GOLD",
            "source": "COMEX",
            "timeframe": "1h",
            "timestamp": "2026-09-01T00:00:00Z",
            "open": 2000.0,
            "high": 2010.0,
            "low": 1990.0,
            "close": 2005.0,
            "volume": 100,
        },
    )
    assert reponse.status_code == 404


def test_bougie_transforme_une_valeur_invalide_en_422(monkeypatch):
    monkeypatch.setattr(main, "obtenir_bougies", lambda instrument_id: [])
    reponse = client.post(
        "/bougie/GOLD",
        json={
            "instrument_id": "GOLD",
            "source": "COMEX",
            "timeframe": "1h",
            "timestamp": "2026-09-01T00:00:00Z",
            "open": 2000.0,
            "high": 2010.0,
            "low": 1990.0,
            "close": 2005.0,
            "volume": 100,
        },
    )
    assert reponse.status_code == 422


# --------------------------------------------------------------------- /backtest et /portefeuille


def test_backtest_instrument_inconnu_renvoie_404():
    reponse = client.get("/backtest/BITCOIN")
    assert reponse.status_code == 404


def test_portefeuille_plafond_invalide_renvoie_422():
    reponse = client.get("/portefeuille?instruments=GOLD&plafond_exposition_ratio=0")
    assert reponse.status_code == 422


def test_portefeuille_propage_l_erreur_de_chargement_des_donnees(monkeypatch):
    """Une HTTPException levée en chargeant les bougies d'un instrument (ex. fixture manquante)
    doit ressortir telle quelle sur /portefeuille, pas être avalée par le except ValueError."""
    monkeypatch.setitem(main.FIXTURES_PAR_INSTRUMENT, "GOLD", "chemin/absent.json")
    reponse = client.get("/portefeuille?instruments=GOLD")
    assert reponse.status_code == 404
