"""Orchestration du signal quantitatif D2 + D4."""

import pandas as pd

from config.instruments import obtenir_config
from contracts.schemas import Bougie, IndicateursTechniques, SignalQuantitatif
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from risk.position_sizing import calculer_risque


def _valeur_ou_none(valeur) -> float | None:
    if valeur is None or pd.isna(valeur):
        return None
    return float(valeur)


def calculer_signal_quantitatif(
    instrument_id: str, bougies: list[Bougie], capital_virtuel: float | None = None
) -> SignalQuantitatif:
    """Produit le signal quantitatif à partir des indicateurs D2 et du risque D4."""
    obtenir_config(instrument_id)
    df = ajouter_indicateurs(bougies_vers_dataframe(bougies), instrument_id)
    derniere = df.iloc[-1]
    indicateurs = IndicateursTechniques(
        sma_20=_valeur_ou_none(derniere["sma_20"]),
        ema_20=_valeur_ou_none(derniere["ema_20"]),
        rsi_14=_valeur_ou_none(derniere["rsi_14"]),
        macd=_valeur_ou_none(derniere["macd"]),
        macd_signal=_valeur_ou_none(derniere["macd_signal"]),
        atr_14=_valeur_ou_none(derniere["atr_14"]),
    )
    risque = calculer_risque(float(derniere["close"]), indicateurs.atr_14, instrument_id, capital_virtuel)
    derniere_bougie = max(bougies, key=lambda bougie: bougie.timestamp)
    return SignalQuantitatif(
        instrument_id=derniere_bougie.instrument_id,
        source=derniere_bougie.source,
        timeframe=derniere_bougie.timeframe,
        timestamp=derniere_bougie.timestamp,
        indicateurs=indicateurs,
        risque=risque,
        validation=None,
    )
