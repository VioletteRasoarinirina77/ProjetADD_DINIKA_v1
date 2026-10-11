
import httpx
import pytest
import respx
from fastapi import HTTPException

import main

BASE_URL = "http://127.0.0.1:8000"


def _candles_depuis_csv():
    return [
        {
            "instrument_id": "ES",
            "source": "databento",
            "timeframe": "1D",
            "timestamp": "2026-09-01T00:00:00Z",
            "open": 6500.0,
            "high": 6510.0,
            "low": 6490.0,
            "close": 6505.0,
            "volume": 1000,
            "open_interest": None,
            "settlement_price": None,
        }
    ]


@respx.mock
def test_obtenir_bougies_via_api_suit_le_protocole_qualite_puis_gaps_puis_candles(
    monkeypatch,
):
    monkeypatch.setenv(
        "PISTE_DATA_API_URL",
        BASE_URL,
    )

    respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(
            200,
            json={"statut": "ok"},
        )
    )

    respx.get(
        f"{BASE_URL}/api/v1/instruments/ES/quality"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "valid": True,
                "errors": [],
            },
        )
    )

    respx.get(
        f"{BASE_URL}/api/v1/instruments/ES/gaps"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "has_gaps": False,
                "gap_count": 0,
                "gaps": [],
                "error": None,
            },
        )
    )

    respx.get(
        f"{BASE_URL}/api/v1/instruments/ES/candles"
    ).mock(
        return_value=httpx.Response(
            200,
            json=_candles_depuis_csv(),
        )
    )

    bougies = main.obtenir_bougies_via_api("ES")

    assert len(bougies) == 1
    assert bougies[0].instrument_id == "ES"
    assert bougies[0].timeframe == "1D"

    # Séquence attendue :
    # health -> quality -> gaps -> candles
    assert respx.calls.call_count == 4

    urls = [
        str(call.request.url)
        for call in respx.calls
    ]

    assert urls[0] == f"{BASE_URL}/health"
    assert urls[1] == f"{BASE_URL}/api/v1/instruments/ES/quality"
    assert urls[2] == f"{BASE_URL}/api/v1/instruments/ES/gaps"
    assert urls[3] == f"{BASE_URL}/api/v1/instruments/ES/candles"


@respx.mock
def test_obtenir_bougies_via_api_refuse_des_donnees_invalidees(
    monkeypatch,
):
    monkeypatch.setenv(
        "PISTE_DATA_API_URL",
        BASE_URL,
    )

    respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(
            200,
            json={"statut": "ok"},
        )
    )

    respx.get(
        f"{BASE_URL}/api/v1/instruments/ES/quality"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "valid": False,
                "errors": [
                    "prix negatif detecte"
                ],
            },
        )
    )

    # La Piste DATA déclare les données invalides.
    # DataRepository lève ValueError.
    # main.py transforme cette erreur en HTTPException 502.
    with pytest.raises(HTTPException) as exc_info:
        main.obtenir_bougies_via_api("ES")

    assert exc_info.value.status_code == 502
    assert "prix negatif detecte" in exc_info.value.detail


@respx.mock
def test_gaps_detectes_sont_journalises_sans_bloquer(
    monkeypatch,
):
    monkeypatch.setenv(
        "PISTE_DATA_API_URL",
        BASE_URL,
    )

    # Données de gaps définies directement dans le test.
    # Les informations de gaps sont définies directement dans le test.
    gaps_reels = {
        "has_gaps": True,
        "gap_count": 1,
        "gaps": [
            {
                "date_debut": "2026-09-02T00:00:00Z",
                "date_fin": "2026-09-03T00:00:00Z",
            }
        ],
        "error": None,
    }

    respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(
            200,
            json={"statut": "ok"},
        )
    )

    respx.get(
        f"{BASE_URL}/api/v1/instruments/ES/quality"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "valid": True,
                "errors": [],
            },
        )
    )

    respx.get(
        f"{BASE_URL}/api/v1/instruments/ES/gaps"
    ).mock(
        return_value=httpx.Response(
            200,
            json=gaps_reels,
        )
    )

    respx.get(
        f"{BASE_URL}/api/v1/instruments/ES/candles"
    ).mock(
        return_value=httpx.Response(
            200,
            json=_candles_depuis_csv(),
        )
    )

    bougies = main.obtenir_bougies_via_api("ES")

    # La présence de gaps ne doit pas bloquer la récupération
    # des bougies.
    assert len(bougies) == 1
    assert bougies[0].instrument_id == "ES"
    assert bougies[0].timeframe == "1D"
