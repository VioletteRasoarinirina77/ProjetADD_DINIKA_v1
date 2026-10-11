"""Tests du rapport de backtest reproductible (traçabilité dataset + SHA-256, déterminisme)."""

import re
import shutil

import pytest

from integration.pack_repository import ErreurIntegritePack
from scripts.generer_rapport_backtest import PACK_PAR_DEFAUT, generer_rapport

SHA_V1_0 = "23af73a8a6160b45ead19c53503bf5ef56b1a010a63535297eecbc4b1dbb83ac"
COURT = {"configurations": [(120, 40)], "dernieres_bougies": 600}


def _sans_date(rapport: str) -> str:
    return re.sub(r"Généré le : .*", "", rapport)


def test_le_rapport_mentionne_version_du_dataset_et_sha256():
    rapport = generer_rapport(**COURT)
    assert "version **1.0**" in rapport
    assert SHA_V1_0 in rapport


def test_le_rapport_est_reproductible_hors_date_de_generation():
    assert _sans_date(generer_rapport(**COURT)) == _sans_date(generer_rapport(**COURT))


def test_le_rapport_affiche_un_drawdown_en_pourcentage_borne():
    rapport = generer_rapport(**COURT)
    ligne = next(ligne for ligne in rapport.splitlines() if ligne.startswith("| 120 |"))
    drawdown = float(ligne.split("|")[-2].strip().rstrip("%"))
    assert 0.0 <= drawdown <= 100.0


def test_le_rapport_precise_qu_il_ne_promet_aucun_gain():
    assert "aucun de ces résultats n'est une promesse de gain" in generer_rapport(**COURT)


def test_un_dataset_modifie_bloque_la_generation_du_rapport(tmp_path):
    copie = tmp_path / "pack"
    shutil.copytree(PACK_PAR_DEFAUT, copie)
    with open(copie / "dataset" / "ES_quant_daily_v1.0.csv", "ab") as f:
        f.write(b"\n")
    with pytest.raises(ErreurIntegritePack):
        generer_rapport(pack_dir=copie, **COURT)


def test_configuration_sans_trade_est_affichee_n_a():
    rapport = generer_rapport(configurations=[(30, 10)], dernieres_bougies=45)
    assert "| 30 | 10 | 0 | n/a | n/a | n/a |" in rapport


def test_main_ecrit_bien_le_rapport_sur_disque(tmp_path, monkeypatch):
    """A6 : couvre le point d'entrée `python -m scripts.generer_rapport_backtest`."""
    import scripts.generer_rapport_backtest as module

    destination = tmp_path / "rapport.md"
    monkeypatch.setattr(module, "SORTIE_PAR_DEFAUT", destination)
    monkeypatch.setattr(module, "RACINE", tmp_path)
    module.main()
    assert destination.exists()
    assert "Rapport de backtest walk-forward" in destination.read_text(encoding="utf-8")
