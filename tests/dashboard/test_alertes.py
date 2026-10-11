"""Tests de dashboard/alertes.py (D7) : critère CDC "alertes < 5 s" et couverture de chaque
type d'alerte, à partir d'une synthèse construite sur de vraies fixtures (pas de mock des
modèles Pydantic imbriqués -- plus fidèle, et plus simple à maintenir)."""

import json
from pathlib import Path

import pytest

from contracts.schemas import Bougie
from dashboard.alertes import (
    NB_TRADES_MINIMUM_FIABLE,
    SEUIL_ALERTE_SECONDES,
    SEUIL_DRAWDOWN_AVERTISSEMENT,
    SEUIL_DRAWDOWN_CRITIQUE,
    SEUIL_SHARPE_NEGATIF,
    NiveauAlerte,
    generer_alertes,
)
from dashboard.synthese import construire_synthese_panneau_risque
from integration.pack_repository import PackDataRepository
from integration.reconciliation import AnomalieReconciliation

FIXTURES = Path(__file__).parents[2] / "fixtures" / "backtest"
PACK = Path(__file__).parents[2] / "fixtures" / "integration" / "pack_es_v1"


def _charger_bougies(nom_fichier: str) -> list[Bougie]:
    with open(FIXTURES / nom_fichier, encoding="utf-8") as f:
        return [Bougie(**d) for d in json.load(f)]


@pytest.fixture(scope="module")
def synthese_gold():
    """Synthèse GOLD (fixtures synthétiques) : sert de base, dupliquée puis modifiée par test."""
    bougies = _charger_bougies("bougies_gold_150h.json")
    return construire_synthese_panneau_risque("GOLD", bougies, taille_hors_echantillon=30)


@pytest.fixture(scope="module")
def synthese_es_reelle():
    bougies = PackDataRepository(PACK).candles_validees("ES")
    return construire_synthese_panneau_risque(
        "ES", bougies, donnees_issues_du_pack=True, fenetre_max_bougies=1000
    )


# --------------------------------------------------------------------------- critère de temps


def test_alertes_sur_le_pack_reel_es_sous_le_seuil_cdc_de_5_secondes(synthese_es_reelle):
    _, duree = generer_alertes(synthese_es_reelle)
    assert duree < SEUIL_ALERTE_SECONDES


def test_generer_alertes_renvoie_la_duree_mesuree(synthese_gold):
    alertes, duree = generer_alertes(synthese_gold)
    assert isinstance(alertes, list)
    assert duree >= 0.0


# --------------------------------------------------------------------------- alerte : taille nulle


def test_alerte_taille_nulle_reprend_l_explication_de_la_synthese(synthese_gold):
    synthese_a_taille_nulle = synthese_gold.model_copy(
        update={"explication_taille_nulle": "0 contrat recommandé : capital insuffisant."}
    )
    alertes, _ = generer_alertes(synthese_a_taille_nulle)
    codes = {a.code for a in alertes}
    assert "taille_position_nulle" in codes
    alerte = next(a for a in alertes if a.code == "taille_position_nulle")
    assert alerte.niveau == NiveauAlerte.AVERTISSEMENT
    assert alerte.message == synthese_a_taille_nulle.explication_taille_nulle


def test_pas_d_alerte_taille_nulle_si_une_taille_est_recommandee(synthese_gold):
    synthese = synthese_gold.model_copy(update={"explication_taille_nulle": None})
    alertes, _ = generer_alertes(synthese)
    assert "taille_position_nulle" not in {a.code for a in alertes}


# --------------------------------------------------------------------------- alerte : drawdown


def test_drawdown_sous_le_seuil_ne_declenche_aucune_alerte(synthese_gold):
    synthese = synthese_gold.model_copy(update={"drawdown_max": SEUIL_DRAWDOWN_AVERTISSEMENT - 0.01})
    alertes, _ = generer_alertes(synthese)
    assert "drawdown_eleve" not in {a.code for a in alertes}


def test_drawdown_au_dessus_du_seuil_avertissement_declenche_une_alerte(synthese_gold):
    synthese = synthese_gold.model_copy(update={"drawdown_max": SEUIL_DRAWDOWN_AVERTISSEMENT + 0.01})
    alertes, _ = generer_alertes(synthese)
    alerte = next(a for a in alertes if a.code == "drawdown_eleve")
    assert alerte.niveau == NiveauAlerte.AVERTISSEMENT


def test_drawdown_au_dessus_du_seuil_critique_devient_critique(synthese_gold):
    synthese = synthese_gold.model_copy(update={"drawdown_max": SEUIL_DRAWDOWN_CRITIQUE + 0.01})
    alertes, _ = generer_alertes(synthese)
    alerte = next(a for a in alertes if a.code == "drawdown_eleve")
    assert alerte.niveau == NiveauAlerte.CRITIQUE


def test_pas_d_alerte_drawdown_si_le_drawdown_est_absent(synthese_gold):
    synthese = synthese_gold.model_copy(update={"drawdown_max": None})
    alertes, _ = generer_alertes(synthese)
    assert "drawdown_eleve" not in {a.code for a in alertes}


# --------------------------------------------------------------------------- alerte : Sharpe négatif


def test_sharpe_tres_negatif_declenche_une_alerte(synthese_gold):
    synthese = synthese_gold.model_copy(update={"sharpe": SEUIL_SHARPE_NEGATIF - 0.5})
    alertes, _ = generer_alertes(synthese)
    assert "sharpe_negatif" in {a.code for a in alertes}


def test_sharpe_legerement_negatif_ne_declenche_rien(synthese_gold):
    synthese = synthese_gold.model_copy(update={"sharpe": SEUIL_SHARPE_NEGATIF + 0.1})
    alertes, _ = generer_alertes(synthese)
    assert "sharpe_negatif" not in {a.code for a in alertes}


# --------------------------------------------------------------------------- alerte : nombre de trades


def test_aucun_trade_declenche_une_alerte_specifique(synthese_gold):
    synthese = synthese_gold.model_copy(update={"nb_trades": 0})
    alertes, _ = generer_alertes(synthese)
    alerte = next(a for a in alertes if a.code == "aucun_trade")
    assert alerte.niveau == NiveauAlerte.AVERTISSEMENT


def test_peu_de_trades_declenche_une_alerte_info(synthese_gold):
    synthese = synthese_gold.model_copy(update={"nb_trades": NB_TRADES_MINIMUM_FIABLE - 1})
    alertes, _ = generer_alertes(synthese)
    alerte = next(a for a in alertes if a.code == "peu_de_trades")
    assert alerte.niveau == NiveauAlerte.INFO


def test_assez_de_trades_ne_declenche_aucune_alerte_sur_leur_nombre(synthese_gold):
    synthese = synthese_gold.model_copy(update={"nb_trades": NB_TRADES_MINIMUM_FIABLE})
    alertes, _ = generer_alertes(synthese)
    assert {a.code for a in alertes} & {"aucun_trade", "peu_de_trades"} == set()


# --------------------------------------------------------------------------- alerte : ATR indisponible


def test_atr_indisponible_declenche_une_alerte(synthese_gold):
    indicateurs = synthese_gold.signal.indicateurs.model_copy(update={"atr_14": None})
    signal = synthese_gold.signal.model_copy(update={"indicateurs": indicateurs})
    synthese = synthese_gold.model_copy(update={"signal": signal})
    alertes, _ = generer_alertes(synthese)
    assert "atr_indisponible" in {a.code for a in alertes}


def test_atr_disponible_ne_declenche_rien(synthese_gold):
    assert synthese_gold.signal.indicateurs.atr_14 is not None
    alertes, _ = generer_alertes(synthese_gold)
    assert "atr_indisponible" not in {a.code for a in alertes}


# --------------------------------------------------------------------------- alerte : réconciliation


def test_anomalie_de_reconciliation_devient_une_alerte(synthese_gold):
    anomalie = AnomalieReconciliation(
        instrument_id="GOLD",
        timestamp="2026-01-01T00:00:00Z",
        source_a="COMEX",
        close_a=2400.0,
        source_b="OANDA",
        close_b=2450.0,
        ecart_pct=2.08,
    )
    alertes, _ = generer_alertes(synthese_gold, [anomalie])
    alerte = next(a for a in alertes if a.code == "ecart_reconciliation")
    assert alerte.niveau == NiveauAlerte.AVERTISSEMENT
    assert "COMEX" in alerte.message and "OANDA" in alerte.message


def test_anomalie_de_reconciliation_importante_devient_critique(synthese_gold):
    anomalie = AnomalieReconciliation(
        instrument_id="GOLD",
        timestamp="2026-01-01T00:00:00Z",
        source_a="COMEX",
        close_a=2400.0,
        source_b="OANDA",
        close_b=2600.0,
        ecart_pct=8.33,
    )
    alertes, _ = generer_alertes(synthese_gold, [anomalie])
    alerte = next(a for a in alertes if a.code == "ecart_reconciliation")
    assert alerte.niveau == NiveauAlerte.CRITIQUE


def test_pas_d_anomalie_ne_declenche_aucune_alerte_de_reconciliation(synthese_gold):
    alertes, _ = generer_alertes(synthese_gold, [])
    assert "ecart_reconciliation" not in {a.code for a in alertes}


# --------------------------------------------------------------------------- tri par sévérité


def test_les_alertes_sont_triees_critique_avant_avertissement_avant_info(synthese_gold):
    synthese = synthese_gold.model_copy(
        update={
            "nb_trades": NB_TRADES_MINIMUM_FIABLE - 1,  # -> INFO
            "drawdown_max": SEUIL_DRAWDOWN_CRITIQUE + 0.01,  # -> CRITIQUE
            "sharpe": SEUIL_SHARPE_NEGATIF - 0.5,  # -> AVERTISSEMENT
        }
    )
    alertes, _ = generer_alertes(synthese)
    niveaux = [a.niveau for a in alertes]
    assert niveaux == sorted(niveaux, key=lambda n: {"critique": 0, "avertissement": 1, "info": 2}[n])
    assert niveaux[0] == NiveauAlerte.CRITIQUE


# --------------------------------------------------------------------------- instrument inconnu


def test_generer_alertes_leve_une_erreur_pour_un_instrument_inconnu(synthese_gold):
    synthese = synthese_gold.model_copy(update={"instrument_id": "BITCOIN"})
    with pytest.raises(KeyError):
        generer_alertes(synthese)
