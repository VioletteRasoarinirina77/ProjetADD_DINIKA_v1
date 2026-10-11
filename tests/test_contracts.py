"""Tests des schémas du contrat d'interface — utilise les fixtures figées (Sprint 0)."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.schemas import Bougie

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def charger_fixture(nom_fichier: str) -> list[dict]:
    with open(
        FIXTURES_DIR / "contract" / nom_fichier,
        encoding="utf-8",
    ) as f:
        return json.load(f)



def test_les_fixtures_gold_sont_valides():
    """Vérifie que le fichier de fixtures respecte le schéma Bougie — le rendrait
    immédiatement détectable si Harimamy change le format sans nous prévenir."""
    donnees = charger_fixture("bougies_gold_exemple.json")
    bougies = [Bougie(**d) for d in donnees]
    assert len(bougies) == 3
    assert all(b.instrument_id == "GOLD" for b in bougies)


def test_bougie_refuse_high_inferieur_a_low():
    with pytest.raises(ValidationError):
        Bougie(
            instrument_id="GOLD", source="COMEX", timeframe="1h",
            timestamp="2026-08-24T08:00:00Z",
            open=100, high=90, low=95, close=92, volume=10,  # high < low : incohérent
        )


def test_bougie_refuse_timestamp_sans_fuseau_horaire():
    with pytest.raises(ValidationError):
        Bougie(
            instrument_id="GOLD", source="COMEX", timeframe="1h",
            timestamp="2026-08-24T08:00:00",  # pas de "Z" ni d'offset -> naïf, refusé
            open=100, high=105, low=95, close=102, volume=10,
        )


# --- Contrat OHLC complet (les 6 règles) et prix strictement positifs -------


def _bougie(**champs) -> Bougie:
    base = dict(
        instrument_id="ES", source="databento", timeframe="1D",
        timestamp="2026-08-24T08:00:00Z",
        open=100.0, high=110.0, low=90.0, close=105.0, volume=10.0,
    )
    base.update(champs)
    return Bougie(**base)


def test_une_bougie_coherente_est_acceptee():
    assert _bougie().close == 105.0


@pytest.mark.parametrize(
    "champs",
    [
        {"open": 200.0},   # open > high
        {"close": 500.0},  # close > high
        {"open": 10.0},    # open < low
        {"close": 1.0},    # close < low
        {"high": 80.0},    # high < low (déjà couvert par un autre test, revérifié ici)
        {"low": 120.0},    # low > high
    ],
)
def test_bougie_refuse_chaque_violation_des_6_regles_ohlc(champs):
    with pytest.raises(ValidationError):
        _bougie(**champs)


@pytest.mark.parametrize("prix", [0.0, -5.0])
def test_bougie_refuse_des_prix_non_strictement_positifs(prix):
    with pytest.raises(ValidationError):
        _bougie(open=prix, high=prix, low=prix, close=prix)


def test_bougie_refuse_un_settlement_price_non_positif():
    with pytest.raises(ValidationError):
        _bougie(settlement_price=0.0)


def test_bougie_accepte_open_interest_et_settlement_price_absents():
    bougie = _bougie()
    assert bougie.open_interest is None
    assert bougie.settlement_price is None
