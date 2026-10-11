"""Tests de l'adaptateur pack gelé (integration/pack_repository.py).

Vérifie :
- le branchement réel sur un pack DATA (format DINIKA_ES_QUANT_PACK) ;
- le refus explicite si le SHA-256 ne correspond plus au manifest ;
- l'interchangeabilité avec DataRepository (même interface) ;
- que D3 (walk-forward) tourne sans modification sur les bougies produites.
"""

import json
import shutil
from pathlib import Path

import pytest

from backtest.walk_forward import walk_forward_backtest
from contracts.schemas import Bougie
from integration.pack_repository import ErreurIntegritePack, PackDataRepository

PACK_REEL = Path(__file__).parents[2] / "fixtures" / "integration" / "pack_es_v1"


def _pack_disponible() -> bool:
    return (PACK_REEL / "reproducibility" / "DATASET_MANIFEST.json").exists()


pytestmark = pytest.mark.skipif(
    not _pack_disponible(),
    reason="Pack ES réel absent de fixtures/integration/pack_es_v1 (copie locale non versionnée).",
)


def test_candles_validees_charge_les_bougies_reelles():
    repo = PackDataRepository(PACK_REEL)
    bougies = repo.candles_validees("ES")

    assert len(bougies) > 100
    assert all(isinstance(bougie, Bougie) for bougie in bougies)
    assert all(bougie.instrument_id == "ES" for bougie in bougies)
    assert all(bougie.timeframe == "1D" for bougie in bougies)


def test_bougies_triees_chronologiquement():
    repo = PackDataRepository(PACK_REEL)
    bougies = repo.candles_validees("ES")

    timestamps = [bougie.timestamp for bougie in bougies]
    assert timestamps == sorted(timestamps)


def test_instrument_absent_du_pack_leve_une_erreur():
    repo = PackDataRepository(PACK_REEL)

    with pytest.raises(ValueError, match="GOLD"):
        repo.candles_validees("GOLD")


def test_integrite_ok_sur_le_pack_non_modifie():
    repo = PackDataRepository(PACK_REEL)
    repo.verifier_integrite()  # ne doit lever aucune exception


def test_integrite_refuse_un_dataset_modifie(tmp_path):
    """LE test qui prouve la garantie de reproductibilité : si le CSV
    livré est modifié -- même d'un octet -- le pipeline doit s'arrêter
    plutôt que produire un résultat silencieusement différent."""
    pack_copie = tmp_path / "pack_altere"
    shutil.copytree(PACK_REEL, pack_copie)

    chemin_manifest = pack_copie / "reproducibility" / "DATASET_MANIFEST.json"
    with open(chemin_manifest, encoding="utf-8") as fichier:
        manifest = json.load(fichier)

    chemin_dataset = pack_copie / "dataset" / manifest["dataset_name"]
    with open(chemin_dataset, "a", encoding="utf-8") as fichier:
        fichier.write("\n2099-01-01 00:00:00+00:00,databento,ES,0,1,1,1,1,1\n")

    repo = PackDataRepository(pack_copie)

    with pytest.raises(ErreurIntegritePack):
        repo.verifier_integrite()

    with pytest.raises(ErreurIntegritePack):
        repo.candles_validees("ES")


def test_pack_manquant_leve_filenotfounderror(tmp_path):
    with pytest.raises(FileNotFoundError):
        PackDataRepository(tmp_path / "nexiste_pas")


def test_walk_forward_tourne_sans_modification_sur_les_bougies_du_pack():
    """Preuve d'intégration bout en bout : D3 (non modifié) accepte
    directement la sortie de PackDataRepository, comme il accepterait
    celle de DataRepository (même interface, même contrat Bougie)."""
    repo = PackDataRepository(PACK_REEL)
    bougies = repo.candles_validees("ES")

    resultat = walk_forward_backtest(
        bougies,
        "ES",
        taille_train=60,
        taille_test=20,
    )

    assert resultat.nb_trades is not None
    assert resultat.nb_trades > 0


def test_meme_sha256_donne_le_meme_resultat_de_backtest():
    """Preuve de reproductibilité : deux chargements indépendants du même
    pack gelé doivent produire exactement les mêmes métriques."""
    repo_1 = PackDataRepository(PACK_REEL)
    repo_2 = PackDataRepository(PACK_REEL)

    bougies_1 = repo_1.candles_validees("ES")
    bougies_2 = repo_2.candles_validees("ES")

    resultat_1 = walk_forward_backtest(bougies_1, "ES", taille_train=60, taille_test=20)
    resultat_2 = walk_forward_backtest(bougies_2, "ES", taille_train=60, taille_test=20)

    assert resultat_1 == resultat_2


# ---------------------------------------------------------------------------
# Branches d'erreur de quality() et du chargement (contrat de qualité de la
# Piste Data) : chaque défaut déclaré dans QUALITY_REPORT.json doit être refusé.
# ---------------------------------------------------------------------------


def _pack_avec_rapport_qualite(tmp_path, **modifications) -> PackDataRepository:
    """Copie le pack et y altère QUALITY_REPORT.json (le CSV, lui, reste intact :
    l'intégrité SHA-256 passe, seul le rapport de qualité déclare un défaut)."""
    pack_copie = tmp_path / "pack_qualite"
    shutil.copytree(PACK_REEL, pack_copie)
    chemin_rapport = pack_copie / "quality" / "QUALITY_REPORT.json"
    with open(chemin_rapport, encoding="utf-8") as fichier:
        rapport = json.load(fichier)
    rapport.update(modifications)
    with open(chemin_rapport, "w", encoding="utf-8") as fichier:
        json.dump(rapport, fichier)
    return PackDataRepository(pack_copie)


def test_le_pack_officiel_a_une_qualite_valide():
    resultat = PackDataRepository(PACK_REEL).quality("ES")
    assert resultat["valid"] is True
    assert resultat["errors"] == []


@pytest.mark.parametrize(
    "defaut,fragment_message",
    [
        ({"ohlc_invalid_rows": 3}, "OHLC invalide"),
        ({"negative_volume_rows": 2}, "volume(s) négatif(s)"),
        ({"duplicate_timestamp_instrument": 1}, "doublon(s)"),
        ({"chronological": False}, "chronologique"),
        ({"missing_required_columns": ["close"]}, "colonnes obligatoires manquantes"),
    ],
)
def test_quality_signale_chaque_defaut_declare_par_la_piste_data(tmp_path, defaut, fragment_message):
    repo = _pack_avec_rapport_qualite(tmp_path, **defaut)

    resultat = repo.quality("ES")

    assert resultat["valid"] is False
    assert any(fragment_message in erreur for erreur in resultat["errors"])


def test_candles_refuse_un_pack_dont_le_rapport_de_qualite_est_invalide(tmp_path):
    """Un défaut de qualité déclaré bloque le chargement : pas de calcul sur
    des données que la Piste Data elle-même déclare invalides."""
    repo = _pack_avec_rapport_qualite(tmp_path, ohlc_invalid_rows=1)

    with pytest.raises(ValueError, match="invalides"):
        repo.candles("ES")


def test_integrite_leve_filenotfounderror_si_le_csv_est_absent(tmp_path):
    pack_copie = tmp_path / "pack_sans_csv"
    shutil.copytree(PACK_REEL, pack_copie)
    for csv_ in (pack_copie / "dataset").glob("*.csv"):
        csv_.unlink()

    with pytest.raises(FileNotFoundError, match="Dataset introuvable"):
        PackDataRepository(pack_copie).verifier_integrite()


def test_gaps_retourne_les_gaps_documentes_du_pack():
    gaps = PackDataRepository(PACK_REEL).gaps("ES")
    assert gaps  # non vide : 3 gaps calendaires documentés dans v1.0
