"""Adaptateur "pack gelé" pour la Piste DATA (v1.0, mode fichier).

Contexte :
    Le pack livré par Harimamy (DINIKA_ES_QUANT_PACK_v1_0) ne contient
    pas encore de service HTTP -- api/QUANT_API.md du pack dit explicitement
    "Quant lit directement le fichier CSV". `data/repository.py` (DataRepository)
    suppose au contraire une API REST (/health, /quality, /gaps, /candles).

Objectif de ce module :
    Fournir EXACTEMENT la même interface que DataRepository
    (candles_validees(instrument_id) -> list[Bougie]) mais alimentée par
    le pack gelé local, pour que D2 (indicators/), D3 (backtest/) et D4 (risk/)
    n'aient RIEN à changer selon que la donnée vienne de l'API (plus tard)
    ou du pack gelé (aujourd'hui). C'est le même principe que le contrat
    d'interface Bougie : le code métier ne sait pas d'où vient la donnée.

Reproductibilité (exigence du pack, DATA_CONTRACT.md §15-16) :
    Avant tout calcul, on recalcule le SHA-256 du CSV et on le compare à
    celui figé dans reproducibility/DATASET_MANIFEST.json. Si le fichier a
    été modifié -- même un seul octet -- le pipeline s'arrête explicitement
    plutôt que de produire un résultat silencieusement non reproductible.
    Le couple (dataset_version, sha256) utilisé est journalisé (audit/logger.py)
    à chaque appel, pour que tout signal ou résultat de backtest produit
    puisse être retracé jusqu'à la version exacte des données sources.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from audit.logger import journaliser_decision
from contracts.schemas import Bougie
from integration.charger_donnees_pack import charger_bougies_depuis_csv_pack

# Le manifest du pack utilise ses propres noms de fréquence ("daily").
# On les traduit vers la convention interne Quant (cf. config/instruments.py)
# plutôt que de supposer une correspondance implicite.
_MAPPING_FREQUENCE_VERS_TIMEFRAME = {
    "daily": "1D",
    "hourly": "1h",
}





class ErreurIntegritePack(Exception):
    """Levée quand le SHA-256 réel du dataset ne correspond plus au manifest."""


class PackDataRepository:
    """Repository DATA basé sur un pack gelé livré en fichiers locaux.

    Usage :
        repo = PackDataRepository("chemin/vers/quant_pack_v1")
        bougies = repo.candles_validees("ES")

    Interchangeable avec data.repository.DataRepository : même méthode
    candles_validees(instrument_id), même comportement "refuse si invalide".
    """

    def __init__(self, pack_dir: str | Path):
        """Ouvre le pack situé dans `pack_dir` (le contenu n'est lu qu'à l'appel des méthodes)."""
        self.pack_dir = Path(pack_dir)

        if not self.pack_dir.exists():
            raise FileNotFoundError(f"Dossier de pack introuvable : {self.pack_dir}")

        self._manifest = self._charger_manifest()

    # ------------------------------------------------------------------
    # Manifest et intégrité
    # ------------------------------------------------------------------

    def _charger_manifest(self) -> dict:
        chemin = self.pack_dir / "reproducibility" / "DATASET_MANIFEST.json"
        with open(chemin, encoding="utf-8") as fichier:
            return json.load(fichier)

    def _chemin_dataset(self) -> Path:
        return self.pack_dir / "dataset" / self._manifest["dataset_name"]

    def verifier_integrite(self) -> None:
        """Recalcule le SHA-256 du dataset et le compare à celui figé dans le.

        manifest. Lève ErreurIntegritePack si le fichier ne correspond plus --
        condition de reproductibilité, jamais un avertissement silencieux.
        """
        chemin = self._chemin_dataset()

        if not chemin.exists():
            raise FileNotFoundError(f"Dataset introuvable : {chemin}")

        sha_attendu = self._manifest["sha256"]

        hachage = hashlib.sha256()
        with open(chemin, "rb") as fichier:
            for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
                hachage.update(bloc)
        sha_reel = hachage.hexdigest()

        if sha_reel != sha_attendu:
            raise ErreurIntegritePack(
                f"Le dataset {chemin.name} ne correspond plus au manifest "
                f"(attendu {sha_attendu}, obtenu {sha_reel}). "
                f"Le pack v{self._manifest['dataset_version']} est censé être gelé "
                f"(DATA_CONTRACT.md §15) -- ne pas continuer sans vérifier avec "
                f"la Piste DATA."
            )

    # ------------------------------------------------------------------
    # Qualité (équivalent local de DataRepository.quality())
    # ------------------------------------------------------------------

    def quality(self, instrument_id: str) -> dict:
        """Dérive un statut valid/errors à partir de quality/QUALITY_REPORT.json.

        du pack, selon les mêmes critères que ceux documentés dans le
        rapport d'audit DINIKA (§3 : doublons, OHLC invalide, volume négatif,
        ordre chronologique, colonnes obligatoires).
        """
        chemin = self.pack_dir / "quality" / "QUALITY_REPORT.json"

        with open(chemin, encoding="utf-8") as fichier:
            rapport = json.load(fichier)

        erreurs = []

        if rapport.get("ohlc_invalid_rows", 0) != 0:
            erreurs.append(f"{rapport['ohlc_invalid_rows']} ligne(s) OHLC invalide(s)")

        if rapport.get("negative_volume_rows", 0) != 0:
            erreurs.append(f"{rapport['negative_volume_rows']} volume(s) négatif(s)")

        if rapport.get("duplicate_timestamp_instrument", 0) != 0:
            erreurs.append(f"{rapport['duplicate_timestamp_instrument']} doublon(s) timestamp+instrument")

        if rapport.get("chronological") is not True:
            erreurs.append("ordre chronologique non garanti")

        if rapport.get("missing_required_columns"):
            erreurs.append(f"colonnes obligatoires manquantes : {rapport['missing_required_columns']}")

        return {"valid": not erreurs, "errors": erreurs, "rapport_brut": rapport}

    def gaps(self, instrument_id: str) -> dict:
        """Renvoie le contenu brut de quality/GAPS.json (dimanches et jours fériés attendus)."""
        chemin = self.pack_dir / "quality" / "GAPS.json"
        with open(chemin, encoding="utf-8") as fichier:
            return json.load(fichier)

    # ------------------------------------------------------------------
    # Point d'entrée principal, même signature que DataRepository
    # ------------------------------------------------------------------

    def candles(self, instrument_id: str) -> list[Bougie]:
        """Séquence identique à DataRepository.candles() :.

        intégrité -> qualité -> gaps -> bougies.
        """
        instrument_du_pack = self._manifest["instrument"]

        if instrument_id != instrument_du_pack:
            raise ValueError(
                f"Ce pack ne contient que l'instrument {instrument_du_pack!r}, "
                f"pas {instrument_id!r}. Vérifie le pack passé à PackDataRepository."
            )

        # 1. Intégrité -- condition de reproductibilité, avant tout calcul.
        self.verifier_integrite()

        # 2. Qualité.
        quality = self.quality(instrument_id)

        if not quality["valid"]:
            raise ValueError(f"Données DATA invalides pour {instrument_id} : {quality['errors']}")

        # 3. Gaps (chargés pour information / journalisation, non bloquants :
        #    le contrat DATA les documente explicitement comme "non
        #    automatiquement des erreurs").
        gaps = self.gaps(instrument_id)

        # 4. Bougies, converties via le même chargeur CSV que celui déjà
        #    utilisé/testé pour le format Databento (aucune logique dupliquée).
        timeframe = _MAPPING_FREQUENCE_VERS_TIMEFRAME.get(
            self._manifest["frequency"],
            self._manifest["frequency"],
        )

        bougies = charger_bougies_depuis_csv_pack(
            self._chemin_dataset(),
            timeframe=timeframe,
        )



        bougies = sorted(bougies, key=lambda bougie: bougie.timestamp)

        periode = None
        if bougies:
            periode = f"{bougies[0].timestamp.date()} -> {bougies[-1].timestamp.date()}"

        # Traçabilité / reproductibilité : chaque appel journalise la version
        # exacte des données utilisées (jamais juste "ça a marché").
        journaliser_decision(
            "chargement_pack_data",
            instrument_id,
            {
                "dataset_version": self._manifest["dataset_version"],
                "sha256": self._manifest["sha256"],
                "nb_bougies": len(bougies),
                "nb_gaps_calendaires": len(gaps.get("gaps", [])),
                "periode": periode,
            },
        )

        return bougies

    def provenance(self) -> dict:
        """Traçabilité exigée pour tout résultat (backtest, métriques, rapport) :.

        version du dataset gelé et SHA-256, après vérification réelle d'intégrité.
        Lève ErreurIntegritePack si le fichier ne correspond plus au manifest.
        """
        self.verifier_integrite()
        return {
            "dataset_name": self._manifest["dataset_name"],
            "dataset_version": self._manifest["dataset_version"],
            "sha256": self._manifest["sha256"],
            "instrument": self._manifest["instrument"],
            "integrite_verifiee": True,
        }

    def candles_validees(self, instrument_id: str) -> list[Bougie]:
        """Point d'entrée utilisé par D2/D3/D4 -- identique à DataRepository."""
        return self.candles(instrument_id)


if __name__ == "__main__":
    import sys

    chemin_pack = sys.argv[1] if len(sys.argv) > 1 else "quant_pack_v1"

    repo = PackDataRepository(chemin_pack)
    bougies = repo.candles_validees("ES")

    print(f"{len(bougies)} bougies chargées et vérifiées depuis {chemin_pack}")
    print(f"période : {bougies[0].timestamp.date()} -> {bougies[-1].timestamp.date()}")
    print(f"dataset_version={repo._manifest['dataset_version']} sha256={repo._manifest['sha256'][:12]}...")
