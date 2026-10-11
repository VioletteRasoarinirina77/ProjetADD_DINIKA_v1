import math

from indicators.technical import (
    ajouter_indicateurs,
    bougies_vers_dataframe,
)
from integration.pack_repository import PackDataRepository

PACK_PATH = "fixtures/integration/pack_es_v1"


def charger_d2_es():
    """Charge les données ES du PACK puis exécute le traitement D2."""

    repository = PackDataRepository(PACK_PATH)

    bougies = repository.candles_validees("ES")

    df = bougies_vers_dataframe(bougies)

    resultat = ajouter_indicateurs(df, "ES")

    return bougies, resultat


def test_d2_utilise_reellement_le_pack_es():
    """Vérifie que D2 travaille directement sur les données du PACK ES."""

    bougies, df = charger_d2_es()

    assert len(bougies) == 4453
    assert len(df) == 4453

    colonnes_marche = {
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    assert colonnes_marche.issubset(df.columns)

    indicateurs_d2 = {
        "sma_20",
        "ema_20",
        "rsi_14",
        "macd",
        "macd_signal",
        "atr_14",
    }

    assert indicateurs_d2.issubset(df.columns)


def test_d2_es_est_chronologique():
    """Vérifie que les données ES sont dans l'ordre chronologique."""

    _, df = charger_d2_es()

    assert df.index.is_monotonic_increasing


def test_d2_es_produit_des_indicateurs_sur_la_fin_du_dataset():
    """Vérifie que les indicateurs sont disponibles sur la dernière bougie."""

    _, df = charger_d2_es()

    derniere = df.iloc[-1]

    indicateurs_d2 = [
        "sma_20",
        "ema_20",
        "rsi_14",
        "macd",
        "macd_signal",
        "atr_14",
    ]

    for indicateur in indicateurs_d2:
        valeur = float(derniere[indicateur])

        assert math.isfinite(valeur), (
            f"{indicateur} devrait avoir une valeur numérique "
            f"sur la dernière bougie."
        )


def test_d2_es_derniere_bougie_est_bien_celle_du_pack():
    """Vérifie que D2 arrive bien jusqu'à la dernière donnée du PACK."""

    _, df = charger_d2_es()

    derniere = df.iloc[-1]

    assert derniere.name.isoformat().startswith("2026-09-13")


def test_d2_es_resultats_derniere_bougie():
    """Vérifie les résultats D2 de la dernière bougie du PACK ES."""

    _, df = charger_d2_es()

    derniere = df.iloc[-1]

    assert math.isclose(
        float(derniere["sma_20"]),
        7687.5125,
        rel_tol=0.0,
        abs_tol=1e-6,
    )

    assert math.isclose(
        float(derniere["ema_20"]),
        7678.649387899333,
        rel_tol=0.0,
        abs_tol=1e-6,
    )

    assert math.isclose(
        float(derniere["rsi_14"]),
        43.448090957923334,
        rel_tol=0.0,
        abs_tol=1e-6,
    )

    assert math.isclose(
        float(derniere["macd"]),
        -10.68175109015283,
        rel_tol=0.0,
        abs_tol=1e-6,
    )

    assert math.isclose(
        float(derniere["macd_signal"]),
        2.6458700044560657,
        rel_tol=0.0,
        abs_tol=1e-6,
    )

    assert math.isclose(
        float(derniere["atr_14"]),
        61.65291412428577,
        rel_tol=0.0,
        abs_tol=1e-6,
    )
