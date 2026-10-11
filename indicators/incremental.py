"""Calcul incrémental des indicateurs (D2) — exigence CDC : mise à jour < 5 s.

ajouter_indicateurs() (technical.py) recalcule tout l'historique à chaque
appel. C'est adapté au BACKTESTING (D3), qui a besoin de la série entière,
mais moins adapté au flux TEMPS RÉEL.

Ce module maintient un ÉTAT et met à jour uniquement avec la nouvelle
bougie, à coût constant — indépendant de la longueur de l'historique déjà vu.

Les paramètres des indicateurs sont récupérés depuis config/instruments.py,
comme pour technical.py. Il n'y a donc pas de périodes spécifiques à un
instrument codées en dur dans le calcul.

Note :
Les formules suivent l'EMA standard et la méthode de Wilder pour le RSI et
l'ATR. L'amorçage peut différer légèrement de pandas-ta. Les valeurs
convergent ensuite vers le calcul batch.
"""

from pydantic import BaseModel, Field

from config.instruments import obtenir_config
from contracts.schemas import Bougie, IndicateursTechniques


class EtatIndicateurs(BaseModel):
    """État minimal nécessaire pour le calcul incrémental."""

    nb_bougies_vues: int = 0
    derniers_closes: list[float] = Field(default_factory=list)

    ema_20: float | None = None

    ema_12: float | None = None
    ema_26: float | None = None
    macd_signal_ema9: float | None = None

    close_precedent: float | None = None

    moyenne_gains: float | None = None
    moyenne_pertes: float | None = None

    atr_14: float | None = None


def _ema_suivant(
    valeur_precedente: float | None,
    nouvelle_valeur: float,
    periode: int,
) -> float:
    """Calcule la prochaine valeur d'une EMA."""
    alpha = 2 / (periode + 1)

    if valeur_precedente is None:
        return nouvelle_valeur

    return (
        alpha * nouvelle_valeur
        + (1 - alpha) * valeur_precedente
    )


def _wilder_suivant(
    valeur_precedente: float | None,
    nouvelle_valeur: float,
    periode: int,
) -> float:
    """Calcule la prochaine valeur avec le lissage de Wilder."""
    if valeur_precedente is None:
        return nouvelle_valeur

    return (
        valeur_precedente * (periode - 1)
        + nouvelle_valeur
    ) / periode


def mettre_a_jour(
    etat: EtatIndicateurs,
    bougie: Bougie,
) -> tuple[EtatIndicateurs, IndicateursTechniques]:
    """Met à jour les indicateurs à partir d'une seule nouvelle bougie.

    Les périodes sont récupérées depuis la configuration de l'instrument
    indiqué dans bougie.instrument_id.
    """
    # ------------------------------------------------------------------
    # 1. Récupération de la configuration de l'instrument
    # ------------------------------------------------------------------

    config = obtenir_config(bougie.instrument_id)
    p = config.indicateurs

    nouvel_etat = etat.model_copy(deep=True)
    nouvel_etat.nb_bougies_vues += 1

    # ------------------------------------------------------------------
    # 2. SMA
    # ------------------------------------------------------------------

    nouvel_etat.derniers_closes = (
        [*etat.derniers_closes, bougie.close]
        [-p.periode_sma:]
    )

    sma = (
        sum(nouvel_etat.derniers_closes) / p.periode_sma
        if len(nouvel_etat.derniers_closes) == p.periode_sma
        else None
    )

    # ------------------------------------------------------------------
    # 3. EMA
    # ------------------------------------------------------------------

    nouvel_etat.ema_20 = _ema_suivant(
        etat.ema_20,
        bougie.close,
        p.periode_ema,
    )

    ema = (
        nouvel_etat.ema_20
        if nouvel_etat.nb_bougies_vues >= p.periode_ema
        else None
    )

    # ------------------------------------------------------------------
    # 4. MACD
    # ------------------------------------------------------------------

    nouvel_etat.ema_12 = _ema_suivant(
        etat.ema_12,
        bougie.close,
        p.macd_rapide,
    )

    nouvel_etat.ema_26 = _ema_suivant(
        etat.ema_26,
        bougie.close,
        p.macd_lente,
    )

    macd_brut = (
        nouvel_etat.ema_12
        - nouvel_etat.ema_26
    )

    nouvel_etat.macd_signal_ema9 = _ema_suivant(
        etat.macd_signal_ema9,
        macd_brut,
        p.macd_signal,
    )

    historique_macd_suffisant = (
        nouvel_etat.nb_bougies_vues
        >= p.macd_lente + p.macd_signal
    )

    macd = (
        macd_brut
        if historique_macd_suffisant
        else None
    )

    macd_signal = (
        nouvel_etat.macd_signal_ema9
        if historique_macd_suffisant
        else None
    )

    # ------------------------------------------------------------------
    # 5. RSI
    # ------------------------------------------------------------------

    rsi = None

    if etat.close_precedent is not None:
        variation = (
            bougie.close
            - etat.close_precedent
        )

        gain = max(variation, 0.0)
        perte = max(-variation, 0.0)

        nouvel_etat.moyenne_gains = _wilder_suivant(
            etat.moyenne_gains,
            gain,
            p.periode_rsi,
        )

        nouvel_etat.moyenne_pertes = _wilder_suivant(
            etat.moyenne_pertes,
            perte,
            p.periode_rsi,
        )

        if nouvel_etat.nb_bougies_vues > p.periode_rsi:
            if nouvel_etat.moyenne_pertes == 0:
                rsi = 100.0
            else:
                rs = (
                    nouvel_etat.moyenne_gains
                    / nouvel_etat.moyenne_pertes
                )

                rsi = 100 - (
                    100 / (1 + rs)
                )

    # ------------------------------------------------------------------
    # 6. ATR
    # ------------------------------------------------------------------

    atr = None

    if etat.close_precedent is not None:
        vrai_range = max(
            bougie.high - bougie.low,
            abs(
                bougie.high
                - etat.close_precedent
            ),
            abs(
                bougie.low
                - etat.close_precedent
            ),
        )

        nouvel_etat.atr_14 = _wilder_suivant(
            etat.atr_14,
            vrai_range,
            p.periode_atr,
        )

        if nouvel_etat.nb_bougies_vues > p.periode_atr:
            atr = nouvel_etat.atr_14

    # ------------------------------------------------------------------
    # 7. Mise à jour de l'état
    # ------------------------------------------------------------------

    nouvel_etat.close_precedent = bougie.close

    # ------------------------------------------------------------------
    # 8. Construction du contrat D2
    # ------------------------------------------------------------------

    indicateurs = IndicateursTechniques(
        sma_20=sma,
        ema_20=ema,
        rsi_14=rsi,
        macd=macd,
        macd_signal=macd_signal,
        atr_14=atr,
    )

    return nouvel_etat, indicateurs


