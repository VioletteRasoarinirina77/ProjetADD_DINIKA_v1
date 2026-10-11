"""Tests D4 : plafond d'exposition (risk/exposure.py) et niveaux SL/TP (risk/stops.py)."""

import pytest

from config.instruments import obtenir_config
from risk.exposure import limiter_position_par_exposition
from risk.position_sizing import calculer_risque
from risk.stops import calculer_niveaux

# ---------------------------------------------------------------------------
# Plafond d'exposition
# ---------------------------------------------------------------------------


def test_sans_plafond_la_taille_est_inchangee():
    taille, plafond, limitee = limiter_position_par_exposition(3, 2400.0, 100.0, 500_000.0, None)

    assert (taille, plafond, limitee) == (3, None, False)


def test_plafond_reduit_la_taille():
    # plafond = 50 % de 500 000 = 250 000 ; un contrat vaut 240 000 -> 1 contrat max
    taille, plafond, limitee = limiter_position_par_exposition(2, 2400.0, 100.0, 500_000.0, 50.0)

    assert taille == 1
    assert plafond == 250_000.0
    assert limitee is True


def test_plafond_non_atteint_ne_change_rien():
    taille, plafond, limitee = limiter_position_par_exposition(1, 2400.0, 100.0, 500_000.0, 90.0)

    assert taille == 1
    assert plafond == 450_000.0
    assert limitee is False


def test_plafond_inferieur_a_un_contrat_donne_taille_nulle():
    taille, _, limitee = limiter_position_par_exposition(2, 2400.0, 100.0, 500_000.0, 10.0)

    assert taille == 0
    assert limitee is True


def test_valeur_de_contrat_invalide_donne_taille_nulle():
    taille, _, limitee = limiter_position_par_exposition(2, 0.0, 100.0, 500_000.0, 50.0)

    assert taille == 0
    assert limitee is True


def test_calculer_risque_applique_le_plafond_de_la_configuration(monkeypatch):
    risque_config = obtenir_config("GOLD").risque
    monkeypatch.setattr(risque_config, "exposition_max_pourcentage_capital", 50.0)

    resultat = calculer_risque(2400.0, 10.0, "GOLD", 500_000.0)

    assert resultat.taille_position_recommandee == 1
    assert resultat.exposition_limitee is True
    assert resultat.exposition_max_dollars == 250_000.0
    assert resultat.exposition_notionnelle <= 250_000.0


# ---------------------------------------------------------------------------
# Niveaux stop-loss / take-profit
# ---------------------------------------------------------------------------


def test_niveaux_stop_et_objectif():
    distance, stop_loss, take_profit = calculer_niveaux(2400.0, 10.0, 2.0, 2.0)

    assert distance == 20.0
    assert stop_loss == 2380.0
    assert take_profit == 2440.0


def test_stop_plus_loin_quand_l_atr_augmente():
    _, stop_calme, _ = calculer_niveaux(2400.0, 5.0, 2.0, 2.0)
    _, stop_volatil, _ = calculer_niveaux(2400.0, 15.0, 2.0, 2.0)

    assert stop_volatil < stop_calme


@pytest.mark.parametrize(
    "prix, atr, k, ratio",
    [
        (0.0, 10.0, 2.0, 2.0),
        (-5.0, 10.0, 2.0, 2.0),
        (2400.0, 0.0, 2.0, 2.0),
        (2400.0, 10.0, 0.0, 2.0),
        (2400.0, 10.0, 2.0, 0.0),
    ],
)
def test_niveaux_refusent_les_valeurs_invalides(prix, atr, k, ratio):
    with pytest.raises(ValueError):
        calculer_niveaux(prix, atr, k, ratio)
