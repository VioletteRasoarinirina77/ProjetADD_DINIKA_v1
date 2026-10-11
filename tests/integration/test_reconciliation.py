"""Tests de data_quality/reconciliation.py et du champ open_interest de Bougie."""

from datetime import UTC, datetime

from contracts.schemas import Bougie
from integration.reconciliation import comparer_sources


def _bougie(source: str, close: float, instrument_id: str = "GOLD", ts=None) -> Bougie:
    return Bougie(
        instrument_id=instrument_id,
        source=source,
        timeframe="1h",
        timestamp=ts or datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=100,
    )


def test_ecart_important_est_detecte():
    """COMEX à 2400, OANDA à 2450 -> écart de ~2 %, largement au-dessus d'une tolérance de 0.5 %."""
    comex = [_bougie("COMEX", 2400.0)]
    oanda = [_bougie("OANDA", 2450.0)]

    anomalies = comparer_sources(comex, oanda, tolerance_pct=0.5)

    assert len(anomalies) == 1
    assert anomalies[0].source_a == "COMEX"
    assert anomalies[0].source_b == "OANDA"
    assert anomalies[0].ecart_pct > 0.5


def test_ecart_faible_n_est_pas_signale():
    """Un écart normal de spread (0.1 %) ne doit pas déclencher d'alerte."""
    comex = [_bougie("COMEX", 2400.0)]
    oanda = [_bougie("OANDA", 2402.0)]  # ~0.08 % d'écart

    anomalies = comparer_sources(comex, oanda, tolerance_pct=0.5)

    assert anomalies == []


def test_instants_non_communs_sont_ignores_sans_erreur():
    """Séries à des timestamps différents -> aucune comparaison possible, mais pas de crash."""
    comex = [_bougie("COMEX", 2400.0, ts=datetime(2026, 1, 1, 10, 0, tzinfo=UTC))]
    oanda = [_bougie("OANDA", 2450.0, ts=datetime(2026, 1, 1, 11, 0, tzinfo=UTC))]

    assert comparer_sources(comex, oanda) == []


def test_instruments_differents_ne_sont_jamais_compares():
    """Garde-fou : même si les timestamps concordent, 2 instruments différents ne sont jamais comparés."""
    gold = [_bougie("COMEX", 2400.0, instrument_id="GOLD")]
    es = [_bougie("CME", 5800.0, instrument_id="ES", ts=datetime(2026, 1, 1, 10, 0, tzinfo=UTC))]

    assert comparer_sources(gold, es) == []


def test_bougie_accepte_open_interest_optionnel():
    """Le champ open_interest est optionnel : une Bougie sans OI (CFD, crypto) doit rester valide."""
    sans_oi = _bougie("OANDA", 2400.0)
    assert sans_oi.open_interest is None

    avec_oi = Bougie(
        instrument_id="GOLD", source="COMEX", timeframe="1h",
        timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        open=2400, high=2401, low=2399, close=2400.5, volume=100,
        open_interest=45230,
    )
    assert avec_oi.open_interest == 45230
