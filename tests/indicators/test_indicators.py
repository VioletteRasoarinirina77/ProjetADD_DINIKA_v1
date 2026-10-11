"""
Tests de indicators/technical.py.

La fixture GOLD de 30 bougies permet d'avoir suffisamment
d'historique pour tester SMA-20, RSI-14 et ATR-14.
"""

import json
from pathlib import Path

import pytest

from contracts.schemas import Bougie
from indicators.technical import (
    ajouter_indicateurs,
    bougies_vers_dataframe,
)
from risk.position_sizing import calculer_risque
from services.quant_engine import calculer_signal_quantitatif

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures"


def charger_bougies_30h() -> list[Bougie]:
    with open(
        FIXTURES_DIR / "indicators" / "bougies_gold_30h.json",
        encoding="utf-8",
    ) as f:
        donnees = json.load(f)

    return [
        Bougie(**d)
        for d in donnees
    ]


def test_bougies_vers_dataframe_est_trie_par_date_croissante():
    bougies = charger_bougies_30h()

    df = bougies_vers_dataframe(
        list(reversed(bougies))
    )

    assert df.index.is_monotonic_increasing


def test_bougies_vers_dataframe_refuse_une_liste_vide():
    with pytest.raises(ValueError):
        bougies_vers_dataframe([])


def test_indicateurs_disponibles_avec_assez_d_historique():
    """
    Avec 30 bougies, SMA-20/RSI-14/ATR-14
    doivent être calculés.
    """

    df = ajouter_indicateurs(
        bougies_vers_dataframe(
            charger_bougies_30h()
        ),
        "GOLD",
    )

    derniere = df.iloc[-1]

    assert derniere["sma_20"] is not None
    assert derniere["rsi_14"] is not None
    assert derniere["atr_14"] is not None

    assert 0 <= derniere["rsi_14"] <= 100


def test_indicateur_absent_sans_assez_d_historique():
    """
    Avec seulement 3 bougies, les indicateurs nécessitant
    davantage d'historique doivent rester indisponibles.
    """

    bougies = charger_bougies_30h()[:3]

    signal = calculer_signal_quantitatif(
        "GOLD",
        bougies,
    )

    assert signal.indicateurs.sma_20 is None
    assert signal.indicateurs.rsi_14 is None
    assert signal.indicateurs.atr_14 is None


def test_calculer_risque_sans_atr_renvoie_position_nulle():
    """
    Aucun ATR => aucune taille de position inventée.
    """

    risque = calculer_risque(
        prix_entree=2400.0,
        atr=None,
        instrument_id="GOLD",
    )

    assert risque.taille_position_recommandee == 0


def test_calculer_risque_bloque_si_un_contrat_depasse_le_risque_max():
    """
    Avec 10 000 $ de capital et 1 % de risque :
        risque maximum = 100 $.

    Avec GOLD :
        ATR = 10
        k = 2
        distance stop = 20
        multiplicateur = 100

        risque par contrat = 2 000 $.

    Un contrat dépasse donc le risque autorisé.
    La taille doit être 0.
    """

    risque = calculer_risque(
        prix_entree=2400.0,
        atr=10.0,
        instrument_id="GOLD",
    )

    assert risque.stop_loss < 2400.0
    assert 2400.0 < risque.take_profit

    assert risque.risque_max_dollars == 100.0
    assert risque.risque_par_contrat == 2000.0

    assert risque.taille_position_recommandee == 0


def test_calculer_risque_autorise_des_contrats_si_risque_compatible():
    """
    Vérifie qu'une position entière peut être calculée lorsque
    le capital permet de respecter le risque maximum.
    """

    risque = calculer_risque(
        prix_entree=2400.0,
        atr=1.0,
        instrument_id="GOLD",
        capital_virtuel=50_000.0,
    )

    assert risque.stop_loss < 2400.0
    assert 2400.0 < risque.take_profit

    assert risque.risque_max_dollars == 500.0
    assert risque.risque_par_contrat == 200.0

    assert risque.taille_position_recommandee == 2

    assert (
        risque.risque_par_contrat
        * risque.taille_position_recommandee
        <= risque.risque_max_dollars
    )


def test_signal_quantitatif_porte_la_meme_cle_que_la_derniere_bougie():
    """
    Le signal doit correspondre à la dernière bougie.
    """

    bougies = charger_bougies_30h()

    signal = calculer_signal_quantitatif(
        "GOLD",
        bougies,
    )

    derniere_bougie = max(
        bougies,
        key=lambda b: b.timestamp,
    )

    assert (
        signal.instrument_id
        == derniere_bougie.instrument_id
    )

    assert (
        signal.timestamp
        == derniere_bougie.timestamp
    )


def test_signal_quantitatif_refuse_instrument_inconnu():
    bougies = charger_bougies_30h()

    with pytest.raises(KeyError):
        calculer_signal_quantitatif(
            "INSTRUMENT_INCONNU",
            bougies,
        )
