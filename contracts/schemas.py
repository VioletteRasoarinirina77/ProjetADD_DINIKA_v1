"""Contrats d'interface de la Piste Quant.

Ce fichier définit les schémas échangés entre les différentes pistes
du projet DINIKA.

Entrées :
- Bougie : données OHLCV provenant de la Piste DATA.

Sorties :
- SignalQuantitatif : résultat fourni à la Piste IA/Décision et au dashboard.
- ParametresRisqueCalcules : résultat de la gestion du risque D4.
- ValidationBacktest : résumé du backtest walk-forward D3.

IMPORTANT :
Les paramètres structurants du projet doivent être validés par l'encadreur
avant d'être considérés comme définitivement figés.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class Bougie(BaseModel):
    """Une bougie OHLCV provenant de la Piste DATA."""

    instrument_id: str
    source: str
    timeframe: str
    timestamp: datetime

    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    open_interest: float | None = Field(
        default=None,
        ge=0,
    )

    settlement_price: float | None = Field(
        default=None,
        gt=0,
    )

    @field_validator("timestamp")
    @classmethod
    def doit_etre_utc(cls, valeur: datetime) -> datetime:
        """Garantit que le timestamp est timezone-aware.

        et converti en UTC.
        """
        if valeur.tzinfo is None:
            raise ValueError(
                "Le timestamp doit être timezone-aware (UTC), "
                "jamais naïf."
            )

        return valeur.astimezone(UTC)

    @model_validator(mode="after")
    def verifier_coherence_prix(self):
        """Vérifie les 6 règles OHLC du contrat de données (DATA_CONTRACT.md §OHLC).

        high doit être le plus haut de la bougie et low le plus bas : toute
        valeur qui contredit cela signale une donnée corrompue, jamais un cas
        de marché valide.
        """
        plus_haut_attendu = max(self.open, self.close, self.low)
        if self.high < plus_haut_attendu:
            raise ValueError(
                f"high ({self.high}) doit être >= open ({self.open}), "
                f"close ({self.close}) et low ({self.low}) — donnée corrompue."
            )

        plus_bas_attendu = min(self.open, self.close, self.high)
        if self.low > plus_bas_attendu:
            raise ValueError(
                f"low ({self.low}) doit être <= open ({self.open}), "
                f"close ({self.close}) et high ({self.high}) — donnée corrompue."
            )

        return self


class IndicateursTechniques(BaseModel):
    """Sortie D2.

    Les champs correspondent au contrat actuellement retenu
    pour la Piste Quant.
    """

    sma_20: float | None = None
    ema_20: float | None = None
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    atr_14: float | None = None


class ParametresRisqueCalcules(BaseModel):
    """Résultat du calcul de risque D4.

    La taille de position est exprimée en nombre entier
    de contrats.
    """

    taille_position_recommandee: int = Field(
        ge=0,
    )

    stop_loss: float

    take_profit: float

    capital_virtuel: float = Field(
        gt=0,
    )

    risque_max_dollars: float = Field(
        ge=0,
    )

    risque_par_contrat: float = Field(
        ge=0,
    )

    exposition_notionnelle: float = Field(
        ge=0,
    )

    pourcentage_risque_engage: float = Field(
        ge=0,
    )

    exposition_max_dollars: float | None = Field(
        default=None,
        ge=0,
    )

    exposition_limitee: bool = False


class ValidationBacktest(BaseModel):
    """Résumé de D3.

    Les métriques sont calculées par le module de backtesting
    walk-forward et peuvent être absentes pour un signal temps réel.
    """

    sharpe: float | None = None
    drawdown_max: float | None = None
    taux_reussite: float | None = None
    nb_trades: int | None = None


class SignalQuantitatif(BaseModel):
    """Résultat principal de la Piste Quant.

    Le signal conserve la même clé d'identification que
    la bougie d'origine afin de permettre le rapprochement
    avec les pistes IA/Décision et Dashboard.
    """

    instrument_id: str
    source: str
    timeframe: str
    timestamp: datetime

    indicateurs: IndicateursTechniques
    risque: ParametresRisqueCalcules
    validation: ValidationBacktest | None = None


if __name__ == "__main__":
    bougie = Bougie(
        instrument_id="GOLD",
        source="COMEX",
        timeframe="1h",
        timestamp=datetime.now(UTC),
        open=2400.0,
        high=2410.0,
        low=2395.0,
        close=2405.0,
        volume=1523,
    )

    signal = SignalQuantitatif(
        instrument_id=bougie.instrument_id,
        source=bougie.source,
        timeframe=bougie.timeframe,
        timestamp=bougie.timestamp,
        indicateurs=IndicateursTechniques(
            rsi_14=58.3,
            atr_14=12.4,
        ),
        risque=ParametresRisqueCalcules(
            taille_position_recommandee=4,
            stop_loss=2380.4,
            take_profit=2429.8,
            capital_virtuel=10_000.0,
            risque_max_dollars=100.0,
            risque_par_contrat=24.8,
            exposition_notionnelle=48_000.0,
            pourcentage_risque_engage=0.01,
        ),
    )

    print(signal.model_dump_json(indent=2))
