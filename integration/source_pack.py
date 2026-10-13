"""SOURCE UNIQUE des données de marché ES : le PACK ES gelé (DINIKA_ES_QUANT_PACK v1.0).

Tout le code qui a besoin de bougies ES réelles passe par CE module : l'API (`main.py`), le tableau de
bord D7, le script de rapport D3, les démonstrations. Il n'existe plus qu'un seul endroit où le chemin du
pack est écrit, qu'une seule variable d'environnement pour le changer (``DINIKA_PACK_DIR``) et qu'une
seule façon de charger les bougies : ``PackDataRepository.candles_validees``, qui vérifie le SHA-256 du
CSV et le rapport de qualité AVANT de rendre la moindre bougie.

Évolution vers le temps réel : une source live devra fournir les mêmes objets ``Bougie`` (contrat
``contracts/schemas.py``) et la même méthode ``candles_validees(instrument_id)``. Le pack reste alors
l'historique de chauffe et la référence de reproductibilité ; aucun calcul (D2/D3/D4/D7/D8) n'a à changer.

Les fixtures JSON (``fixtures/backtest/*.json``) sont des données SYNTHÉTIQUES réservées aux tests : aucun
code d'exécution ne doit les utiliser pour ES (garde-fou : ``tests/test_source_unique.py``).
"""

from __future__ import annotations

import os
from pathlib import Path

from contracts.schemas import Bougie
from integration.pack_repository import PackDataRepository

RACINE_PROJET = Path(__file__).resolve().parent.parent
PACK_DIR_DEFAUT = RACINE_PROJET / "fixtures" / "integration" / "pack_es_v1"
VARIABLE_ENV_PACK = "DINIKA_PACK_DIR"


def dossier_pack() -> Path:
    """Dossier du pack : ``DINIKA_PACK_DIR`` s'il est défini, sinon le pack versionné du dépôt."""
    return Path(os.getenv(VARIABLE_ENV_PACK, str(PACK_DIR_DEFAUT)))


def creer_repository_pack(dossier: str | Path | None = None) -> PackDataRepository:
    """Repository sur le pack gelé (intégrité SHA-256, qualité, trous, provenance)."""
    return PackDataRepository(dossier if dossier is not None else dossier_pack())


def charger_bougies_pack(instrument_id: str = "ES", dossier: str | Path | None = None) -> list[Bougie]:
    """Bougies validées et triées du pack. Le SHA-256 est vérifié AVANT tout calcul.

    Lève ``ErreurIntegritePack`` si le CSV a été modifié, ``FileNotFoundError`` si le pack est absent.
    """
    return creer_repository_pack(dossier).candles_validees(instrument_id)