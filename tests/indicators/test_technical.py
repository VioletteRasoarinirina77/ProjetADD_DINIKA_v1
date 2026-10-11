import math
from datetime import UTC, datetime, timedelta

import pytest

from contracts.schemas import Bougie
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from risk.position_sizing import calculer_risque
from services.quant_engine import calculer_signal_quantitatif


def creer_bougies_gold(nombre: int = 40) -> list[Bougie]:
    """
    Crée un jeu de bougies GOLD déterministe
    pour tester D2 et D4.
    """

    bougies = []

    prix = 2400.0

    date_depart = datetime(
        2026,
        8,
        1,
        0,
        0,
        tzinfo=UTC,
    )

    for i in range(nombre):
        open_price = prix
        close_price = prix + 1.0
        high_price = close_price + 2.0
        low_price = open_price - 2.0

        timestamp = date_depart + timedelta(hours=i)

        bougies.append(
            Bougie(
                instrument_id="GOLD",
                source="COMEX",
                timeframe="1h",
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1000 + i,
            )
        )

        prix = close_price

    return bougies


# ============================================================
# D2 — Conversion des données
# ============================================================


def test_bougies_vers_dataframe_trie_les_dates():
    bougies = creer_bougies_gold()

    # On inverse volontairement l'ordre.
    bougies = list(reversed(bougies))

    df = bougies_vers_dataframe(bougies)

    assert len(df) == 40
    assert df.index.is_monotonic_increasing


def test_bougies_vers_dataframe_refuse_liste_vide():
    with pytest.raises(ValueError):
        bougies_vers_dataframe([])


# ============================================================
# D2 — Indicateurs techniques
# ============================================================


def test_ajouter_indicateurs_cree_les_indicateurs_d2():
    bougies = creer_bougies_gold()
    df = bougies_vers_dataframe(bougies)

    resultat = ajouter_indicateurs(
        df,
        "GOLD",
    )

    assert "sma_20" in resultat.columns
    assert "ema_20" in resultat.columns
    assert "rsi_14" in resultat.columns
    assert "macd" in resultat.columns
    assert "macd_signal" in resultat.columns
    assert "atr_14" in resultat.columns


def test_indicateurs_d2_deviennent_disponibles_apres_assez_de_bougies():
    bougies = creer_bougies_gold(60)

    df = bougies_vers_dataframe(bougies)

    resultat = ajouter_indicateurs(
        df,
        "GOLD",
    )

    derniere = resultat.iloc[-1]

    assert not math.isnan(derniere["sma_20"])
    assert not math.isnan(derniere["ema_20"])
    assert not math.isnan(derniere["rsi_14"])
    assert not math.isnan(derniere["atr_14"])


# ============================================================
# D4 — Validation des paramètres
# ============================================================


def test_calculer_risque_refuse_capital_invalide():
    with pytest.raises(ValueError):
        calculer_risque(
            prix_entree=2400.0,
            atr=10.0,
            instrument_id="GOLD",
            capital_virtuel=0,
        )


def test_calculer_risque_refuse_prix_entree_invalide():
    with pytest.raises(ValueError):
        calculer_risque(
            prix_entree=0,
            atr=10.0,
            instrument_id="GOLD",
            capital_virtuel=10_000.0,
        )


def test_calculer_risque_refuse_multiplicateur_atr_invalide():
    with pytest.raises(ValueError):
        calculer_risque(
            prix_entree=2400.0,
            atr=10.0,
            instrument_id="GOLD",
            capital_virtuel=10_000.0,
            multiplicateur_atr_stop_override=0,
        )


# ============================================================
# D4 — ATR indisponible
# ============================================================


def test_calculer_risque_sans_atr_ne_prend_pas_de_position():
    resultat = calculer_risque(
        prix_entree=2400.0,
        atr=None,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
    )

    assert resultat.taille_position_recommandee == 0
    assert resultat.risque_max_dollars == 0.0
    assert resultat.risque_par_contrat == 0.0
    assert resultat.exposition_notionnelle == 0.0


def test_calculer_risque_avec_atr_zero_ne_prend_pas_de_position():
    resultat = calculer_risque(
        prix_entree=2400.0,
        atr=0.0,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
    )

    assert resultat.taille_position_recommandee == 0


# ============================================================
# D4 — Risque par trade
# ============================================================


def test_calculer_risque_respecte_le_risque_maximal():
    resultat = calculer_risque(
        prix_entree=2400.0,
        atr=10.0,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
    )

    # GOLD = 1 % du capital par défaut.
    assert resultat.risque_max_dollars == 100.0

    risque_reel = (
        resultat.taille_position_recommandee
        * resultat.risque_par_contrat
    )

    assert risque_reel <= resultat.risque_max_dollars


def test_taille_position_est_un_entier():
    resultat = calculer_risque(
        prix_entree=2400.0,
        atr=10.0,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
    )

    assert isinstance(
        resultat.taille_position_recommandee,
        int,
    )

    assert resultat.taille_position_recommandee >= 0


# ============================================================
# D4 — Stop Loss / Take Profit
# ============================================================


def test_stop_loss_est_base_sur_atr():
    prix_entree = 2400.0
    atr = 10.0

    resultat = calculer_risque(
        prix_entree=prix_entree,
        atr=atr,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
        multiplicateur_atr_stop_override=2.0,
    )

    distance_attendue = atr * 2.0

    assert resultat.stop_loss == pytest.approx(
        prix_entree - distance_attendue,
        abs=0.01,
    )


def test_take_profit_respecte_le_ratio_risque_gain():
    prix_entree = 2400.0
    atr = 10.0

    resultat = calculer_risque(
        prix_entree=prix_entree,
        atr=atr,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
        multiplicateur_atr_stop_override=2.0,
    )

    distance_stop = atr * 2.0

    distance_tp = (
        resultat.take_profit - prix_entree
    )

    assert distance_tp == pytest.approx(
        distance_stop * 2.0,
        abs=0.01,
    )


# ============================================================
# D4 — Risque par contrat
# ============================================================


def test_risque_par_contrat_utilise_le_multiplicateur_du_contrat():
    prix_entree = 2400.0
    atr = 10.0
    multiplicateur_atr = 2.0

    resultat = calculer_risque(
        prix_entree=prix_entree,
        atr=atr,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
        multiplicateur_atr_stop_override=multiplicateur_atr,
    )

    distance_stop = atr * multiplicateur_atr

    # GOLD : multiplicateur contrat = 100.
    risque_attendu = distance_stop * 100.0

    assert resultat.risque_par_contrat == pytest.approx(
        risque_attendu,
        abs=0.01,
    )


# ============================================================
# D4 — Exposition
# ============================================================


def test_exposition_notionnelle_est_coherente():
    prix_entree = 2400.0

    resultat = calculer_risque(
        prix_entree=prix_entree,
        atr=10.0,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
    )

    exposition_attendue = (
        resultat.taille_position_recommandee
        * prix_entree
        * 100.0
    )

    assert resultat.exposition_notionnelle == pytest.approx(
        exposition_attendue,
        abs=0.01,
    )


# ============================================================
# D4 — Risque réellement engagé
# ============================================================


def test_pourcentage_risque_engage_est_coherent():
    resultat = calculer_risque(
        prix_entree=2400.0,
        atr=10.0,
        instrument_id="GOLD",
        capital_virtuel=10_000.0,
    )

    risque_reel = (
        resultat.taille_position_recommandee
        * resultat.risque_par_contrat
    )

    pourcentage_attendu = (
        risque_reel / 10_000.0
    )

    # Ce test documente le comportement souhaité D4.
    assert resultat.pourcentage_risque_engage == pytest.approx(
        pourcentage_attendu,
        abs=0.000001,
    )


# ============================================================
# D2 + D4 — Signal complet
# ============================================================


def test_calculer_signal_quantitatif_retourne_signal_complet():
    bougies = creer_bougies_gold(60)

    signal = calculer_signal_quantitatif(
        instrument_id="GOLD",
        bougies=bougies,
        capital_virtuel=10_000.0,
    )

    assert signal.instrument_id == "GOLD"
    assert signal.source == "COMEX"
    assert signal.timeframe == "1h"

    # D2
    assert signal.indicateurs.sma_20 is not None
    assert signal.indicateurs.ema_20 is not None
    assert signal.indicateurs.rsi_14 is not None
    assert signal.indicateurs.atr_14 is not None

    # D4
    assert signal.risque.capital_virtuel == 10_000.0
    assert signal.risque.taille_position_recommandee >= 0


def test_calculer_signal_quantitatif_est_deterministe():
    bougies = creer_bougies_gold(60)

    signal1 = calculer_signal_quantitatif(
        "GOLD",
        bougies,
        capital_virtuel=10_000.0,
    )

    signal2 = calculer_signal_quantitatif(
        "GOLD",
        bougies,
        capital_virtuel=10_000.0,
    )

    assert signal1.model_dump() == signal2.model_dump()
