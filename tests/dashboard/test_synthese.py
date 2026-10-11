"""Tests de la synthèse du panneau D7 (critères CDC : bandeau permanent, < 3 s)."""

import json
from pathlib import Path

import pytest

from config.instruments import OrigineDonnees
from contracts.schemas import Bougie
from dashboard.synthese import (
    BANDEAU_AVERTISSEMENT,
    SEUIL_SYNTHESE_SECONDES,
    construire_synthese_panneau_risque,
    expliquer_taille_nulle,
    libelle_origine_donnees,
)
from integration.pack_repository import PackDataRepository
from risk.position_sizing import calculer_risque

FIXTURES = Path(__file__).parents[2] / "fixtures" / "backtest"


def _bougies(nom: str) -> list[Bougie]:
    with open(FIXTURES / nom) as f:
        return [Bougie(**d) for d in json.load(f)]


@pytest.fixture(scope="module")
def synthese_gold():
    return construire_synthese_panneau_risque("GOLD", _bougies("bougies_gold_300h.json"))


def test_la_synthese_est_calculee_en_moins_de_3_secondes(synthese_gold):
    """Critère CDC D7 : synthèse affichée en moins de 3 secondes."""
    assert synthese_gold.duree_calcul_secondes < SEUIL_SYNTHESE_SECONDES


def test_le_bandeau_d_avertissement_accompagne_toujours_la_synthese(synthese_gold):
    assert synthese_gold.bandeau_avertissement == BANDEAU_AVERTISSEMENT
    assert "aucune exécution d'ordre réel" in synthese_gold.bandeau_avertissement


def test_le_bandeau_ne_promet_aucun_gain():
    assert "aucune promesse de gain" in BANDEAU_AVERTISSEMENT


def test_gold_est_presente_comme_synthetique(synthese_gold):
    assert synthese_gold.origine_donnees is OrigineDonnees.SYNTHETIQUE
    assert "SYNTHÉTIQUES" in synthese_gold.libelle_origine


def test_le_libelle_d_origine_de_es_est_reel_gele():
    assert "réelles gelées" in libelle_origine_donnees("ES")


def test_es_alimentee_par_une_fixture_est_presentee_comme_synthetique():
    """Garde-fou : ES est déclarée réelle en config, mais si les bougies
    affichées viennent d'une fixture, le panneau ne doit PAS parler de données réelles."""
    synthese = construire_synthese_panneau_risque("ES", _bougies("bougies_es_300h.json"))
    assert synthese.origine_donnees is OrigineDonnees.SYNTHETIQUE
    assert "SYNTHÉTIQUES" in synthese.libelle_origine


def test_es_alimentee_par_le_pack_est_presentee_comme_reelle():
    synthese = construire_synthese_panneau_risque(
        "ES", _bougies("bougies_es_300h.json"), donnees_issues_du_pack=True
    )
    assert synthese.origine_donnees is OrigineDonnees.REEL_GELE


def test_gold_n_est_jamais_presentee_comme_reelle_meme_si_on_l_affirme():
    synthese = construire_synthese_panneau_risque(
        "GOLD", _bougies("bougies_gold_300h.json"), donnees_issues_du_pack=True
    )
    assert synthese.origine_donnees is OrigineDonnees.SYNTHETIQUE


def test_la_synthese_contient_le_signal_et_les_metriques_de_validation(synthese_gold):
    assert synthese_gold.signal.instrument_id == "GOLD"
    assert synthese_gold.nb_trades >= 0
    if synthese_gold.nb_trades > 0:
        assert synthese_gold.drawdown_max is not None


def test_une_synthese_sur_un_instrument_inconnu_est_refusee():
    with pytest.raises(KeyError):
        construire_synthese_panneau_risque("INCONNU", _bougies("bougies_gold_300h.json"))


def test_le_walk_forward_du_panneau_n_utilise_pas_la_zone_hors_echantillon():
    """Réduire la zone hors-échantillon change la zone de validation : la
    synthèse doit donc pouvoir différer -- preuve que la découpe est bien appliquée."""
    bougies = _bougies("bougies_gold_300h.json")
    petite = construire_synthese_panneau_risque("GOLD", bougies, taille_hors_echantillon=10)
    grande = construire_synthese_panneau_risque("GOLD", bougies, taille_hors_echantillon=120)
    assert (petite.nb_trades, petite.sharpe) != (grande.nb_trades, grande.sharpe) or petite.nb_trades == 0


PACK = Path(__file__).parents[2] / "fixtures" / "integration" / "pack_es_v1"


@pytest.fixture(scope="module")
def bougies_pack_es():
    return PackDataRepository(PACK).candles_validees("ES")


def test_taille_nulle_es_10000_dollars_est_expliquee_avec_les_chiffres(bougies_pack_es):
    synthese = construire_synthese_panneau_risque(
        "ES", bougies_pack_es, donnees_issues_du_pack=True, fenetre_max_bougies=300
    )
    assert synthese.signal.risque.taille_position_recommandee == 0
    texte = synthese.explication_taille_nulle
    assert texte is not None
    assert "0 contrat recommandé" in texte
    assert f"{synthese.signal.risque.risque_par_contrat:,.0f}" in texte
    assert "Capital virtuel minimal pour 1 contrat" in texte


def test_pas_d_explication_quand_au_moins_un_contrat_est_recommande(bougies_pack_es):
    synthese = construire_synthese_panneau_risque(
        "ES",
        bougies_pack_es,
        donnees_issues_du_pack=True,
        capital_virtuel=5_000_000.0,
        fenetre_max_bougies=300,
    )
    assert synthese.signal.risque.taille_position_recommandee >= 1
    assert synthese.explication_taille_nulle is None


def test_le_capital_minimal_annonce_permet_bien_un_contrat(bougies_pack_es):
    """Cohérence chiffrée : au capital minimal annoncé, la taille recommandée passe à 1."""
    synthese = construire_synthese_panneau_risque(
        "ES", bougies_pack_es, donnees_issues_du_pack=True, fenetre_max_bougies=300
    )
    rpc = synthese.signal.risque.risque_par_contrat
    capital_min = rpc / 0.01  # pourcentage_risque_par_trade d'ES dans config/instruments.py
    atr = synthese.signal.indicateurs.atr_14
    risque = calculer_risque(bougies_pack_es[-1].close, atr, "ES", capital_min * 1.001)
    assert risque.taille_position_recommandee == 1


def test_explication_atr_indisponible():
    from contracts.schemas import ParametresRisqueCalcules

    risque = ParametresRisqueCalcules(
        taille_position_recommandee=0, stop_loss=1.0, take_profit=1.0, capital_virtuel=10_000.0,
        risque_max_dollars=0.0, risque_par_contrat=0.0, exposition_notionnelle=0.0,
        pourcentage_risque_engage=0.0,
    )
    assert "ATR indisponible" in expliquer_taille_nulle("ES", risque)


def test_la_fenetre_limite_le_nombre_de_bougies_analysees(bougies_pack_es):
    synthese = construire_synthese_panneau_risque(
        "ES", bougies_pack_es, donnees_issues_du_pack=True, fenetre_max_bougies=400
    )
    assert synthese.nb_bougies_analysees == 400
    assert synthese.signal.timestamp == bougies_pack_es[-1].timestamp  # bougies les plus récentes


def test_synthese_sur_le_pack_reel_es_sous_le_seuil_cdc_de_3_secondes(bougies_pack_es):
    """Critère CDC D7 vérifié sur les vraies données (fenêtre du panneau : 1000 bougies)."""
    synthese = construire_synthese_panneau_risque(
        "ES", bougies_pack_es, donnees_issues_du_pack=True, fenetre_max_bougies=1000
    )
    assert synthese.origine_donnees is OrigineDonnees.REEL_GELE
    assert synthese.duree_calcul_secondes < SEUIL_SYNTHESE_SECONDES
    assert 0.0 <= synthese.drawdown_max <= 1.0
