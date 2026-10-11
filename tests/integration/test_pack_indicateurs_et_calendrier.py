"""Points de revue 28 et 29 sur le pack officiel ES v1.0.

- Point 28 : aucune ligne du dimanche ne doit être perdue à l'ingestion.
- Point 29 : recoupement des indicateurs D2 (calcul indépendant) avec les
  colonnes de référence présentes dans le CSV de la Piste Data.
"""

from pathlib import Path

import pandas as pd
import pytest

from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from integration.pack_repository import PackDataRepository

PACK_REEL = Path(__file__).parents[2] / "fixtures" / "integration" / "pack_es_v1"
CSV_REEL = PACK_REEL / "dataset" / "ES_quant_daily_v1.0.csv"

pytestmark = pytest.mark.skipif(not CSV_REEL.exists(), reason="Pack ES réel absent.")


@pytest.fixture(scope="module")
def bougies_pack():
    return PackDataRepository(PACK_REEL).candles_validees("ES")


@pytest.fixture(scope="module")
def indicateurs_d2(bougies_pack):
    return ajouter_indicateurs(bougies_vers_dataframe(bougies_pack), "ES")


@pytest.fixture(scope="module")
def reference_csv():
    return pd.read_csv(CSV_REEL, parse_dates=["timestamp"]).set_index("timestamp")


def test_aucune_ligne_n_est_perdue_a_l_ingestion(bougies_pack, reference_csv):
    """4453 lignes dans le CSV gelé = 4453 bougies validées (point 28)."""
    assert len(bougies_pack) == len(reference_csv) == 4453


def test_les_bougies_du_dimanche_sont_conservees(bougies_pack):
    """Le dataset contient des timestamps de dimanche (session CME du soir) :
    aucun filtre 'jours ouvrés' ne doit les supprimer (contrainte 8)."""
    dimanches = [b for b in bougies_pack if b.timestamp.weekday() == 6]
    assert len(dimanches) == 744


def test_sma_20_de_d2_est_identique_a_la_reference_de_la_piste_data(indicateurs_d2, reference_csv):
    ecart = (indicateurs_d2["sma_20"] - reference_csv["sma_20"].reindex(indicateurs_d2.index)).abs()
    assert ecart.dropna().max() < 1e-9


def test_ema_20_de_d2_converge_vers_la_reference_apres_chauffe(indicateurs_d2, reference_csv):
    """L'EMA dépend de son initialisation : écart toléré pendant la chauffe,
    négligeable après 100 bougies."""
    ecart = (indicateurs_d2["ema_20"] - reference_csv["ema_20"].reindex(indicateurs_d2.index)).abs()
    assert ecart.dropna().iloc[100:].max() < 0.01


@pytest.mark.parametrize("colonne,correlation_min", [("atr_14", 0.95), ("rsi_14", 0.85)])
def test_atr_et_rsi_de_d2_restent_fortement_correles_a_la_reference(
    indicateurs_d2, reference_csv, colonne, correlation_min
):
    """Écart de VALEUR documenté (docs/decisions.md, D-003) : D2 lisse en
    Wilder (pandas_ta), la Piste Data en moyenne simple. On vérifie donc la
    cohérence de forme, pas l'égalité, et on ne 'corrige' pas silencieusement."""
    correlation = indicateurs_d2[colonne].corr(reference_csv[colonne].reindex(indicateurs_d2.index))
    assert correlation > correlation_min
