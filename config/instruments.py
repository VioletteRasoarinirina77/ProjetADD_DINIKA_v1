"""Configuration paramétrique par instrument — PISTE QUANT (D2/D3/D4).

Objectif de ce fichier :
Éviter le piège classique du débutant qui code "pour un instrument" puis
duplique son code pour chaque nouvel instrument.

Tout ce qui varie d'un instrument à l'autre est isolé dans UNE configuration :
- paramètres des indicateurs ;
- source de données ;
- multiplicateur du contrat ;
- timeframe ;
- paramètres de risque.

Le code des indicateurs, du backtesting et du risque doit lire ces valeurs
ici et ne pas les recopier "en dur".
"""

import os
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class TypeSource(StrEnum):
    """Nature de la source de données."""

    FUTURE = "future"
    CFD = "cfd"
    SPOT_CRYPTO = "spot_crypto"


class OrigineDonnees(StrEnum):
    """Distingue un instrument réellement adossé à un dataset gelé livré par la.

    Piste Data (contrat de données signé, SHA-256 vérifiable, voir
    integration/pack_repository.py) d'un instrument encore synthétique,
    utilisé uniquement pour les fixtures et les tests (point de revue 4).

    Un instrument non explicitement marqué REEL_GELE ne doit jamais être
    utilisé pour produire un signal, un backtest ou un mémoire présentés
    comme fondés sur des données réelles.
    """

    REEL_GELE = "reel_gele"
    SYNTHETIQUE = "synthetique"


class ParametresIndicateurs(BaseModel):
    """Paramètres des indicateurs techniques D2."""

    periode_sma: int = Field(20, gt=0)
    periode_ema: int = Field(20, gt=0)
    periode_rsi: int = Field(14, gt=0)
    periode_atr: int = Field(14, gt=0)

    macd_rapide: int = Field(12, gt=0)
    macd_lente: int = Field(26, gt=0)
    macd_signal: int = Field(9, gt=0)


class SourceDonnees(BaseModel):
    """Une source de données associée à un instrument."""

    nom: str
    symbole: str
    type_source: TypeSource
    est_primaire: bool = False


class ParametresRisque(BaseModel):
    """Paramètres de gestion du risque D4.

    Les valeurs par défaut constituent des paramètres de travail
    et doivent être validées par l'encadreur avant d'être considérées
    comme définitivement figées.
    """

    pourcentage_risque_par_trade: float = Field(
        0.01,
        gt=0,
        le=0.05,
    )

    multiplicateur_atr_stop: float = Field(
        2.0,
        gt=0,
    )

    ratio_risque_gain: float = Field(
        2.0,
        gt=0,
    )

    # Limite optionnelle de l'exposition notionnelle
    # exprimée en pourcentage du capital.
    # None = aucune limite activée.
    exposition_max_pourcentage_capital: float | None = Field(
        default=None,
        gt=0,
    )


class InstrumentConfig(BaseModel):
    """Configuration complète d'un instrument."""

    instrument_id: str

    indicateurs: ParametresIndicateurs = Field(
        default_factory=ParametresIndicateurs
    )

    devise: str = "USD"

    multiplicateur_contrat: float

    timeframe_defaut: str = "1h"

    spread_points: float = Field(
        0.5,
        ge=0,
    )

    sources: list[SourceDonnees]

    risque: ParametresRisque = Field(
        default_factory=ParametresRisque
    )

    # Capital virtuel par défaut de l'instrument (D-012) : configurable, jamais figé dans le code
    # de calcul. Le dimensionnement reste automatique (nombre ENTIER de contrats, 1 % de risque).
    capital_virtuel_defaut: float = Field(10_000.0, gt=0)

    # Défaut volontairement prudent : un instrument ajouté sans préciser ce
    # champ est traité comme SYNTHETIQUE tant qu'un pack gelé réel n'a pas
    # été livré et vérifié -- jamais l'inverse.
    origine_donnees: OrigineDonnees = OrigineDonnees.SYNTHETIQUE

    @model_validator(mode="after")
    def une_seule_source_primaire(self):
        """Un instrument doit avoir exactement une source primaire."""
        primaires = [
            source
            for source in self.sources
            if source.est_primaire
        ]

        if len(primaires) != 1:
            raise ValueError(
                f"{self.instrument_id} doit avoir EXACTEMENT une source "
                f"primaire (trouvé: {len(primaires)}). "
                f"Corrige la config avant de continuer."
            )

        return self

    def source_primaire(self) -> SourceDonnees:
        """Retourne la source primaire de l'instrument."""
        return next(
            source
            for source in self.sources
            if source.est_primaire
        )


# ---------------------------------------------------------------------------
# REGISTRE DES INSTRUMENTS
# ---------------------------------------------------------------------------

INSTRUMENTS: dict[str, InstrumentConfig] = {
    "GOLD": InstrumentConfig(
        instrument_id="GOLD",
        multiplicateur_contrat=100.0,
        timeframe_defaut="1h",
        spread_points=0.30,

        sources=[
            SourceDonnees(
                nom="COMEX",
                symbole="GC",
                type_source=TypeSource.FUTURE,
                est_primaire=True,
            ),
            SourceDonnees(
                nom="OANDA",
                symbole="XAUUSD",
                type_source=TypeSource.CFD,
                est_primaire=False,
            ),
        ],

        risque=ParametresRisque(
            pourcentage_risque_par_trade=0.01,
            multiplicateur_atr_stop=2.0,
            ratio_risque_gain=2.0,
        ),

        # Aucun pack gelé COMEX livré à ce jour -- GOLD ne sert que pour les
        # fixtures/tests (fixtures/backtest/bougies_gold_*.json), jamais pour
        # un résultat présenté comme réel dans un mémoire ou un backtest final.
        origine_donnees=OrigineDonnees.SYNTHETIQUE,
    ),

    "ES": InstrumentConfig(
        instrument_id="ES",
        multiplicateur_contrat=50.0,
        timeframe_defaut="1D",
        spread_points=0.50,

        indicateurs=ParametresIndicateurs(
            periode_sma=20,
            periode_ema=20,
            periode_rsi=14,
            periode_atr=14,
            macd_rapide=12,
            macd_lente=26,
            macd_signal=9,
        ),

        sources=[
            SourceDonnees(
                nom="databento",
                symbole="ES.v.0",
                type_source=TypeSource.FUTURE,
                est_primaire=True,
            ),
        ],

        risque=ParametresRisque(
            pourcentage_risque_par_trade=0.01,
            multiplicateur_atr_stop=2.5,
            ratio_risque_gain=2.0,
        ),

        # D-012 : contrat ES standard (50 $/point), 1 % de risque par trade, taille automatique.
        # Un contrat ES représente ~7 700 $ de risque (stop 2,5 x ATR) : il faut ~770 000 $ pour qu'il
        # passe sous 1 % ; 2 M$ garde une taille >= 1 sur 78 des 79 trades historiques (mesuré, k = 2,5).
        # Valeur modifiable ici, par DINIKA_CAPITAL_VIRTUEL ou par paramètre d'appel.
        capital_virtuel_defaut=2_000_000.0,

        # Dataset gelé v1.0 réellement livré par la Piste Data et vérifié par
        # SHA-256 (voir integration/pack_repository.py et
        # fixtures/integration/pack_es_v1/reproducibility/DATASET_MANIFEST.json).
        origine_donnees=OrigineDonnees.REEL_GELE,
    ),
}


VARIABLE_ENV_CAPITAL = "DINIKA_CAPITAL_VIRTUEL"


def resoudre_capital_virtuel(instrument_id: str, capital_virtuel: float | None = None) -> float:
    """Capital virtuel effectif (D-012). Priorité : valeur explicite > variable d'environnement.

    `DINIKA_CAPITAL_VIRTUEL` > `capital_virtuel_defaut` de l'instrument dans ce registre.
    """
    if capital_virtuel is not None:
        return float(capital_virtuel)
    valeur_env = os.getenv(VARIABLE_ENV_CAPITAL)
    if valeur_env:
        try:
            capital = float(valeur_env)
        except ValueError as erreur:
            raise ValueError(f"{VARIABLE_ENV_CAPITAL} doit être un nombre, reçu : {valeur_env!r}") from erreur
        if capital <= 0:
            raise ValueError(f"{VARIABLE_ENV_CAPITAL} doit être strictement positif.")
        return capital
    return obtenir_config(instrument_id).capital_virtuel_defaut


def resoudre_capital_portefeuille(instrument_ids: list[str], capital: float | None = None) -> float:
    """Capital d'un portefeuille multi-instruments : valeur explicite > variable d'environnement >.

    plus grand `capital_virtuel_defaut` des instruments demandés (capital partagé).
    """
    if capital is not None or os.getenv(VARIABLE_ENV_CAPITAL):
        return resoudre_capital_virtuel(instrument_ids[0] if instrument_ids else "ES", capital)
    return max((obtenir_config(i).capital_virtuel_defaut for i in instrument_ids), default=10_000.0)


def instruments_avec_donnees_reelles() -> list[str]:
    """Liste les instruments adossés à un dataset gelé réel (par opposition aux.

    instruments synthétiques utilisés uniquement en fixtures/tests).

    Point d'entrée à utiliser par tout code -- dashboard, rapport de
    backtest, mémoire -- avant de présenter un résultat comme fondé sur des
    données réelles plutôt que sur des fixtures de développement.
    """
    return [
        instrument_id
        for instrument_id, config in INSTRUMENTS.items()
        if config.origine_donnees is OrigineDonnees.REEL_GELE
    ]


def obtenir_config(instrument_id: str) -> InstrumentConfig:
    """Point d'entrée unique utilisé par D2/D3/D4."""
    if instrument_id not in INSTRUMENTS:
        raise KeyError(
            f"Instrument inconnu : {instrument_id}. "
            f"Ajoute-le au registre INSTRUMENTS."
        )

    return INSTRUMENTS[instrument_id]


if __name__ == "__main__":
    for iid in INSTRUMENTS:
        cfg = obtenir_config(iid)

        print(
            f"{iid}: source primaire = "
            f"{cfg.source_primaire().nom}:"
            f"{cfg.source_primaire().symbole}, "
            f"risque = "
            f"{cfg.risque.pourcentage_risque_par_trade:.0%} "
            f"par trade"
        )
