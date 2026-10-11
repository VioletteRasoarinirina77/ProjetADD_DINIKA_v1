"""Tests de la correction "validation hors-échantillon" (D8).

Ces tests vérifient précisément ce que le CDC exige et que la première
version ne garantissait pas : que D8 ne rejoue jamais des données déjà
utilisées pour valider D3.
"""

import json
from pathlib import Path

import pytest

from backtest.walk_forward import walk_forward_backtest
from contracts.schemas import Bougie
from paper_trading.simulator import (
    separer_validation_et_hors_echantillon,
    simuler_paper_trading_hors_echantillon,
)

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"


def charger_bougies(nom_fichier: str) -> list[Bougie]:
    with open(FIXTURES_DIR / "backtest" / nom_fichier, encoding="utf-8") as f:
        donnees = json.load(f)
    return [Bougie(**d) for d in donnees]


def test_separation_ne_perd_et_ne_duplique_aucune_bougie():
    bougies = charger_bougies("bougies_gold_300h.json")
    validation, hors_echantillon = separer_validation_et_hors_echantillon(bougies, 60)
    assert len(validation) + len(hors_echantillon) == len(bougies)
    assert len(hors_echantillon) == 60


def test_zone_hors_echantillon_est_strictement_apres_la_zone_de_validation():
    """LE test qui prouve l'absence de chevauchement -- coeur de la correction."""
    bougies = charger_bougies("bougies_gold_300h.json")
    validation, hors_echantillon = separer_validation_et_hors_echantillon(bougies, 60)
    assert validation[-1].timestamp < hors_echantillon[0].timestamp


def test_separation_refuse_une_taille_hors_echantillon_trop_grande():
    bougies = charger_bougies("bougies_gold_300h.json")
    with pytest.raises(ValueError):
        separer_validation_et_hors_echantillon(bougies, taille_hors_echantillon=len(bougies))


def test_walk_forward_sur_la_zone_de_validation_ne_voit_jamais_le_hors_echantillon():
    """Preuve d'intégration : on fait tourner D3 (walk_forward_backtest, non
    modifié) uniquement sur la zone de validation, et on vérifie qu'aucune de
    ses fenêtres internes ne peut dépasser dans la zone hors-échantillon."""
    bougies = charger_bougies("bougies_gold_300h.json")
    validation, hors_echantillon = separer_validation_et_hors_echantillon(bougies, 60)

    resultat_d3 = walk_forward_backtest(validation, "GOLD", taille_train=60, taille_test=20)

    assert resultat_d3.nb_trades is not None
    # Aucune bougie de "validation" ne partage de timestamp avec "hors_echantillon"
    timestamps_validation = {b.timestamp for b in validation}
    timestamps_hors_echantillon = {b.timestamp for b in hors_echantillon}
    assert timestamps_validation.isdisjoint(timestamps_hors_echantillon)


def test_resultat_porte_bien_la_date_de_debut_du_hors_echantillon():
    bougies = charger_bougies("bougies_gold_300h.json")
    resultat = simuler_paper_trading_hors_echantillon(bougies, "GOLD", taille_hors_echantillon=60)
    _, hors_echantillon = separer_validation_et_hors_echantillon(bougies, 60)
    assert resultat.debut_zone_hors_echantillon == hors_echantillon[0].timestamp


def test_fonctionne_sur_es_aussi():
    bougies = charger_bougies("bougies_es_300h.json")
    resultat = simuler_paper_trading_hors_echantillon(bougies, "ES", taille_hors_echantillon=60)
    assert resultat.instrument_id == "ES"
    assert resultat.debut_zone_hors_echantillon is not None


def test_leve_erreur_si_lhistorique_est_trop_court_pour_le_decoupage():
    bougies = charger_bougies("bougies_gold_150h.json")  # 150 bougies seulement
    with pytest.raises(ValueError):
        simuler_paper_trading_hors_echantillon(bougies, "GOLD", taille_hors_echantillon=200)


# --- Point de revue 11 : D8 doit utiliser le paramètre calibré par D3 ---


def test_d8_utilise_le_multiplicateur_calibre_sur_la_zone_de_validation():
    """Le k utilisé en hors-échantillon doit être exactement celui que D3
    calibre sur la zone de validation -- pas la valeur par défaut de la config."""
    from backtest.walk_forward import calibrer_multiplicateur_atr
    from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe

    bougies = charger_bougies("bougies_gold_300h.json")
    resultat = simuler_paper_trading_hors_echantillon(bougies, "GOLD", taille_hors_echantillon=60)

    validation, hors_echantillon = separer_validation_et_hors_echantillon(bougies, 60)
    df = ajouter_indicateurs(bougies_vers_dataframe(bougies), "GOLD")
    df_validation = df.loc[df.index < hors_echantillon[0].timestamp]
    k_attendu = calibrer_multiplicateur_atr(df_validation, "GOLD", 10_000.0)

    assert resultat.multiplicateur_atr_utilise == k_attendu


def test_d8_ne_calibre_jamais_sur_la_zone_hors_echantillon():
    """Anti-fuite : modifier radicalement les bougies hors-échantillon ne doit
    pas changer le multiplicateur calibré (il ne dépend que de la validation)."""
    bougies = charger_bougies("bougies_gold_300h.json")
    reference = simuler_paper_trading_hors_echantillon(bougies, "GOLD", taille_hors_echantillon=60)

    _, hors_echantillon = separer_validation_et_hors_echantillon(bougies, 60)
    debut = hors_echantillon[0].timestamp
    modifiees = [
        b.model_copy(
            update={champ: getattr(b, champ) * 1.3 for champ in ("open", "high", "low", "close")}
        )
        if b.timestamp >= debut
        else b
        for b in bougies
    ]
    resultat = simuler_paper_trading_hors_echantillon(modifiees, "GOLD", taille_hors_echantillon=60)

    assert resultat.multiplicateur_atr_utilise == reference.multiplicateur_atr_utilise


def test_d8_expose_un_multiplicateur_atr_appartenant_aux_candidats_de_d3():
    from backtest.walk_forward import CANDIDATS_MULTIPLICATEUR_ATR

    bougies = charger_bougies("bougies_es_300h.json")
    resultat = simuler_paper_trading_hors_echantillon(bougies, "ES", taille_hors_echantillon=60)
    assert resultat.multiplicateur_atr_utilise in CANDIDATS_MULTIPLICATEUR_ATR
