"""Tests paramétrés sur 2 instruments (GOLD, ES) — preuve que D2/D3/D4 sont
réellement génériques, conformément à la checklist du guide partie 3, §7 :
"étends au deuxième instrument, vérifie que rien n'a été codé en dur".
"""

import json
from pathlib import Path

import pytest

from backtest.walk_forward import walk_forward_backtest
from contracts.schemas import Bougie
from services.quant_engine import calculer_signal_quantitatif

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"



FIXTURES_PAR_INSTRUMENT = {
    "GOLD": "backtest/bougies_gold_150h.json",
    "ES": "backtest/bougies_es_150h.json",
}

def charger_bougies(instrument_id: str) -> list[Bougie]:
    with open(FIXTURES_DIR / FIXTURES_PAR_INSTRUMENT[instrument_id]) as f:
        donnees = json.load(f)

    return [Bougie(**d) for d in donnees]


@pytest.mark.parametrize("instrument_id", ["GOLD", "ES"])
def test_calculer_signal_quantitatif_fonctionne_sur_chaque_instrument(
    instrument_id,
):
    """Le même code, sans aucune branche 'if instrument_id == ...',
    doit produire un signal cohérent pour n'importe quel instrument
    du registre.
    """
    bougies = charger_bougies(instrument_id)
    signal = calculer_signal_quantitatif(instrument_id, bougies)

    assert signal.instrument_id == instrument_id
    assert signal.indicateurs.sma_20 is not None
    assert signal.indicateurs.atr_14 is not None

    # Le pourcentage de risque engagé doit correspondre
    # au risque réellement pris par les contrats calculés.
    risque_reel = (
        signal.risque.taille_position_recommandee
        * signal.risque.risque_par_contrat
    )

    pourcentage_attendu = (
        risque_reel / signal.risque.capital_virtuel
    )

    assert signal.risque.pourcentage_risque_engage == pytest.approx(
        pourcentage_attendu,
        abs=0.000001,
    )


@pytest.mark.parametrize("instrument_id", ["GOLD", "ES"])
def test_walk_forward_backtest_fonctionne_sur_chaque_instrument(
    instrument_id,
):
    bougies = charger_bougies(instrument_id)

    resultat = walk_forward_backtest(
        bougies,
        instrument_id,
        taille_train=60,
        taille_test=20,
    )

    assert resultat.nb_trades is not None

    if resultat.nb_trades > 0:
        assert 0.0 <= resultat.taux_reussite <= 1.0


def test_les_deux_instruments_ont_des_parametres_de_risque_differents():
    """Confirme que le multiplicateur ATR-stop n'est PAS partagé/copier
    entre instruments.

    GOLD = 2.0
    ES   = 2.5

    Cela vérifie que les paramètres de risque proviennent bien
    de la configuration propre à chaque instrument.
    """
    from config.instruments import obtenir_config

    gold_k = obtenir_config("GOLD").risque.multiplicateur_atr_stop
    es_k = obtenir_config("ES").risque.multiplicateur_atr_stop

    assert gold_k != es_k
