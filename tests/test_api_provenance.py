"""Tests de traçabilité des données (version du dataset + SHA-256) — mode ENVIRONMENT=pack."""

import os
import shutil

import pytest
from fastapi.testclient import TestClient

import main
from integration.pack_repository import PackDataRepository

SHA_V1_0 = "23af73a8a6160b45ead19c53503bf5ef56b1a010a63535297eecbc4b1dbb83ac"

client = TestClient(main.app)


@pytest.fixture
def mode_pack(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "pack")


def test_provenance_es_en_mode_pack_donne_version_et_sha256(mode_pack):
    corps = client.get("/provenance/ES").json()
    assert corps["origine_donnees"] == "reel_gele"
    assert corps["dataset_version"] == "1.0"
    assert corps["sha256"] == SHA_V1_0
    assert corps["integrite_verifiee"] is True


def test_provenance_gold_reste_synthetique_sans_hash(mode_pack):
    corps = client.get("/provenance/GOLD").json()
    assert corps["origine_donnees"] == "synthetique"
    assert corps["sha256"] is None


def test_provenance_instrument_inconnu_renvoie_404():
    assert client.get("/provenance/INCONNU").status_code == 404


def test_backtest_es_en_mode_pack_utilise_le_dataset_reel(mode_pack):
    reponse = client.get("/backtest/ES?taille_train=250&taille_test=60")
    assert reponse.status_code == 200
    assert reponse.json()["nb_trades"] >= 0


def test_pack_corrompu_renvoie_503_et_ne_calcule_rien(mode_pack, monkeypatch, tmp_path):
    copie = tmp_path / "pack"
    shutil.copytree(main.PACK_DIR_DEFAUT, copie)
    with open(copie / "dataset" / "ES_quant_daily_v1.0.csv", "ab") as f:
        f.write(b"\n")  # modification d'un octet : le hash ne correspond plus
    monkeypatch.setenv("DINIKA_PACK_DIR", str(copie))
    assert client.get("/backtest/ES?taille_train=250&taille_test=60").status_code == 503
    assert client.get("/provenance/ES").status_code == 503


def test_provenance_du_repository_verifie_reellement_l_integrite():
    repo = PackDataRepository(main.PACK_DIR_DEFAUT)
    assert repo.provenance()["sha256"] == SHA_V1_0


def test_le_mode_dev_utilise_bien_le_pack_pour_es(monkeypatch):
    """obtenir_bougies() lit exclusivement le pack pour ES, y compris en dev
    (seul GOLD, synthétique, passe par les fixtures) -- /provenance doit annoncer
    la même chose que ce qui est réellement chargé."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    corps = client.get("/provenance/ES").json()
    assert corps["dataset_version"] == "1.0"
    assert corps["sha256"] == SHA_V1_0


def test_en_mode_dev_es_est_bien_presentee_comme_reelle():
    """Régression (sens inverse de l'ancien bug) : annoncer « synthetique » pour
    des données qui viennent en réalité du pack gelé tromperait le journal
    d'audit et les consommateurs de /provenance. obtenir_bougies() charge le
    pack pour ES dès que ENVIRONMENT != prod (dev, pack, ou absent) -- la
    provenance doit donc être identique dans ces trois cas."""
    for environnement in ("dev", "pack", None):
        if environnement is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = environnement
        corps = client.get("/provenance/ES").json()
        assert corps["origine_donnees"] == "reel_gele", f"environnement={environnement!r}"
        assert corps["sha256"] == SHA_V1_0, f"environnement={environnement!r}"


def test_gold_reste_synthetique_en_mode_dev(monkeypatch):
    """GOLD n'a aucun pack réel : toujours servie par les fixtures, jamais confondue avec ES."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    corps = client.get("/provenance/GOLD").json()
    assert corps["origine_donnees"] == "synthetique"
    assert corps["sha256"] is None


def test_en_mode_prod_l_origine_suit_la_config_sans_hash(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    corps = main._provenance_donnees("ES")
    assert corps == {"origine_donnees": "reel_gele", "dataset_version": None, "sha256": None}
    assert main._provenance_donnees("GOLD")["origine_donnees"] == "synthetique"
