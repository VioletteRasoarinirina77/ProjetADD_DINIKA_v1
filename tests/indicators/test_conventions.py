"""Tests de indicators/conventions.py et de sa mise en application (D2 batch + incrémental).

Exigences CDC visées : « valeurs reproductibles et testées », « calcul incrémental »,
« aucun paramètre codé en dur ». Les comparaisons batch/incrémental portent sur le PACK ES réel.
"""

import math
from pathlib import Path

import pandas as pd
import pytest

from config.instruments import ParametresIndicateurs
from indicators.conventions import (
    PERIODES_CONTRAT,
    observations_requises,
    verifier_periodes_contrat,
)
from indicators.incremental import EtatIndicateurs, mettre_a_jour
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from integration.pack_repository import PackDataRepository

PACK = Path(__file__).parents[2] / "fixtures" / "integration" / "pack_es_v1"
COLONNES = ["sma_20", "ema_20", "rsi_14", "macd", "macd_signal", "atr_14"]
NB_BOUGIES = 700  # assez pour la chauffe et la convergence, assez court pour rester rapide


@pytest.fixture(scope="module")
def bougies_es():
    """Les NB_BOUGIES premières bougies du PACK ES gelé (SHA-256 vérifié par le repository)."""
    return PackDataRepository(PACK).candles_validees("ES")[:NB_BOUGIES]


@pytest.fixture(scope="module")
def batch(bougies_es):
    return ajouter_indicateurs(bougies_vers_dataframe(bougies_es), "ES")


@pytest.fixture(scope="module")
def incremental(bougies_es, batch):
    etat = EtatIndicateurs()
    lignes = []
    for bougie in bougies_es:
        etat, indicateurs = mettre_a_jour(etat, bougie)
        lignes.append(indicateurs.model_dump())
    return pd.DataFrame(lignes, index=batch.index)


def test_observations_requises_pour_la_configuration_par_defaut():
    assert observations_requises(ParametresIndicateurs()) == {
        "sma_20": 20,
        "ema_20": 20,
        "rsi_14": 15,
        "macd": 26,
        "macd_signal": 34,
        "atr_14": 15,
    }


def test_le_batch_n_emet_aucune_valeur_avant_la_fin_de_la_chauffe(batch):
    for colonne, observations in observations_requises(ParametresIndicateurs()).items():
        assert batch[colonne].iloc[: observations - 1].isna().all(), colonne
        assert not math.isnan(batch[colonne].iloc[observations - 1]), colonne


def test_batch_et_incremental_ont_exactement_la_meme_chauffe(batch, incremental):
    """Avant : RSI 1 NaN (batch) contre 14 (incrémental), MACD 25 contre 34, ATR 13 contre 14."""
    for colonne in COLONNES:
        assert (batch[colonne].isna() == incremental[colonne].isna()).all(), colonne


@pytest.mark.parametrize("colonne", COLONNES)
def test_incremental_et_batch_convergent_apres_la_chauffe(batch, incremental, colonne):
    """Après 500 bougies, l'écart entre les deux calculs est numériquement nul (< 1e-6)."""
    ecart = (batch[colonne] - incremental[colonne]).abs().iloc[500:]
    assert ecart.max() < 1e-6


def test_la_ligne_de_signal_macd_arrive_apres_la_ligne_macd(incremental):
    assert incremental["macd"].notna().idxmax() < incremental["macd_signal"].notna().idxmax()


def test_une_periode_incompatible_avec_les_noms_du_contrat_est_refusee():
    with pytest.raises(ValueError, match="periode_sma=50"):
        verifier_periodes_contrat(ParametresIndicateurs(periode_sma=50))


def test_les_periodes_du_contrat_correspondent_aux_noms_des_champs():
    assert PERIODES_CONTRAT == {
        "periode_sma": 20,
        "periode_ema": 20,
        "periode_rsi": 14,
        "periode_atr": 14,
    }
    verifier_periodes_contrat(ParametresIndicateurs())  # défaut = contrat : aucune erreur