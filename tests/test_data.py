import httpx
import pytest
import respx

from data.repository import DataRepository


@respx.mock
def test_health_appelle_l_api_data():
    route = respx.get("http://data.test/health").mock(
        return_value=httpx.Response(
            200,
            json={"status": "ok"},
        )
    )

    repository = DataRepository("http://data.test")

    resultat = repository.health()

    assert route.called
    assert resultat["status"] == "ok"


@respx.mock
def test_candles_suit_la_sequence_health_quality_gaps_candles():
    health = respx.get("http://data.test/health").mock(
        return_value=httpx.Response(
            200,
            json={"status": "ok"},
        )
    )

    quality = respx.get(
        "http://data.test/api/v1/instruments/ES/quality"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"valid": True, "errors": []},
        )
    )

    gaps = respx.get(
        "http://data.test/api/v1/instruments/ES/gaps"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "has_gaps": True,
                "gap_count": 2,
            },
        )
    )

    candles = respx.get(
        "http://data.test/api/v1/instruments/ES/candles"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "instrument_id": "ES",
                    "source": "databento",
                    "timestamp": "2026-09-02T00:00:00Z",
                    "open": 6400.0,
                    "high": 6450.0,
                    "low": 6380.0,
                    "close": 6430.0,
                    "volume": 1000,
                }
            ],
        )
    )

    repository = DataRepository("http://data.test")

    resultat = repository.candles("ES")

    assert health.called
    assert quality.called
    assert gaps.called
    assert candles.called

    assert len(resultat) == 1
    assert resultat[0].instrument_id == "ES"
    assert resultat[0].timeframe == "1D"


@respx.mock
def test_candles_refuse_donnees_invalides():
    respx.get("http://data.test/health").mock(
        return_value=httpx.Response(
            200,
            json={"status": "ok"},
        )
    )

    respx.get(
        "http://data.test/api/v1/instruments/ES/quality"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "valid": False,
                "errors": ["volume negatif"],
            },
        )
    )

    repository = DataRepository("http://data.test")

    with pytest.raises(ValueError, match="Données DATA invalides"):
        repository.candles("ES")


@respx.mock
def test_candles_convertit_le_timeframe_quotidien():
    respx.get("http://data.test/health").mock(
        return_value=httpx.Response(
            200,
            json={"status": "ok"},
        )
    )

    respx.get(
        "http://data.test/api/v1/instruments/ES/quality"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"valid": True, "errors": []},
        )
    )

    respx.get(
        "http://data.test/api/v1/instruments/ES/gaps"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"has_gaps": False, "gap_count": 0},
        )
    )

    respx.get(
        "http://data.test/api/v1/instruments/ES/candles"
    ).mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "instrument_id": "ES",
                    "source": "databento",
                    "timestamp": "2026-09-03T00:00:00Z",
                    "open": 6400.0,
                    "high": 6450.0,
                    "low": 6380.0,
                    "close": 6430.0,
                    "volume": 1000,
                }
            ],
        )
    )

    repository = DataRepository("http://data.test")

    resultat = repository.candles("ES")

    assert resultat[0].timeframe == "1D"
