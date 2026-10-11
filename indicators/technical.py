"""Calcul des indicateurs techniques D2.

Ce module ne contient que la logique d'indicateurs et de transformation
des bougies en DataFrame. La gestion du risque D4 est dans ``risk/``.
"""

import pandas as pd
import pandas_ta as ta

from config.instruments import obtenir_config
from contracts.schemas import Bougie


def bougies_vers_dataframe(
    bougies: list[Bougie],
) -> pd.DataFrame:
    """Convertit une liste de Bougie en DataFrame trié.

    par timestamp croissant.
    """
    if not bougies:
        raise ValueError(
            "Impossible de calculer un indicateur sans aucune bougie."
        )

    lignes = [
        {
            "timestamp": bougie.timestamp,
            "open": bougie.open,
            "high": bougie.high,
            "low": bougie.low,
            "close": bougie.close,
            "volume": bougie.volume,
        }
        for bougie in bougies
    ]

    return (
        pd.DataFrame(lignes)
        .sort_values("timestamp")
        .set_index("timestamp")
    )

def ajouter_indicateurs(
    df: pd.DataFrame,
    instrument_id: str,
) -> pd.DataFrame:
    """Ajoute les indicateurs techniques D2.

    Les paramètres sont récupérés depuis la configuration
    de l'instrument.
    """
    config = obtenir_config(instrument_id)
    parametres = config.indicateurs

    df = df.copy()

    # SMA
    df["sma_20"] = ta.sma(
        df["close"],
        length=parametres.periode_sma,
    )

    # EMA
    df["ema_20"] = ta.ema(
        df["close"],
        length=parametres.periode_ema,
    )

    # RSI
    df["rsi_14"] = ta.rsi(
        df["close"],
        length=parametres.periode_rsi,
    )

    # MACD
    macd = ta.macd(
        df["close"],
        fast=parametres.macd_rapide,
        slow=parametres.macd_lente,
        signal=parametres.macd_signal,
    )

    if macd is not None and not macd.empty:
        df["macd"] = macd.iloc[:, 0]
        df["macd_signal"] = macd.iloc[:, 2]
    else:
        df["macd"] = None
        df["macd_signal"] = None

    # ATR
    df["atr_14"] = ta.atr(
        df["high"],
        df["low"],
        df["close"],
        length=parametres.periode_atr,
    )

    return df
