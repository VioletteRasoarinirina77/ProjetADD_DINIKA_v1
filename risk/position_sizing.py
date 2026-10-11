"""Composants de gestion du risque D4."""

import math

from config.instruments import obtenir_config, resoudre_capital_virtuel
from contracts.schemas import ParametresRisqueCalcules
from risk.exposure import limiter_position_par_exposition
from risk.stops import calculer_niveaux

# Capital générique de repli (tests, fixtures) : le capital effectif d'un instrument est résolu par
# config.instruments.resoudre_capital_virtuel() (D-012).
CAPITAL_VIRTUEL_DEFAUT = 10_000.0


def calculer_risque(
    prix_entree: float,
    atr: float | None,
    instrument_id: str,
    capital_virtuel: float | None = None,
    multiplicateur_atr_stop_override: float | None = None,
) -> ParametresRisqueCalcules:
    """Calcule taille de position, SL/TP et exposition selon la configuration D4."""
    capital_virtuel = resoudre_capital_virtuel(instrument_id, capital_virtuel)
    if capital_virtuel <= 0:
        raise ValueError("Le capital virtuel doit être strictement positif.")
    if prix_entree <= 0:
        raise ValueError("Le prix d'entrée doit être strictement positif.")
    config = obtenir_config(instrument_id)
    risque = config.risque
    k = (
        multiplicateur_atr_stop_override
        if multiplicateur_atr_stop_override is not None
        else risque.multiplicateur_atr_stop
    )
    if k <= 0:
        raise ValueError("Le multiplicateur ATR du stop doit être strictement positif.")
    if atr is None or atr <= 0:
        return ParametresRisqueCalcules(
            taille_position_recommandee=0,
            stop_loss=prix_entree,
            take_profit=prix_entree,
            capital_virtuel=capital_virtuel,
            risque_max_dollars=0.0,
            risque_par_contrat=0.0,
            exposition_notionnelle=0.0,
            pourcentage_risque_engage=0.0,
            exposition_max_dollars=None,
            exposition_limitee=False,
        )
    distance_stop, stop_loss, take_profit = calculer_niveaux(prix_entree, atr, k, risque.ratio_risque_gain)
    risque_max = capital_virtuel * risque.pourcentage_risque_par_trade
    risque_par_contrat = distance_stop * config.multiplicateur_contrat
    nombre = math.floor(risque_max / risque_par_contrat) if risque_par_contrat > 0 else 0
    nombre, exposition_max, exposition_limitee = limiter_position_par_exposition(
        nombre,
        prix_entree,
        config.multiplicateur_contrat,
        capital_virtuel,
        risque.exposition_max_pourcentage_capital,
    )
    exposition = nombre * prix_entree * config.multiplicateur_contrat
    risque_reel = nombre * risque_par_contrat
    return ParametresRisqueCalcules(
        taille_position_recommandee=nombre,
        stop_loss=round(stop_loss, 2),
        take_profit=round(take_profit, 2),
        capital_virtuel=capital_virtuel,
        risque_max_dollars=round(risque_max, 2),
        risque_par_contrat=round(risque_par_contrat, 2),
        exposition_notionnelle=round(exposition, 2),
        pourcentage_risque_engage=round(risque_reel / capital_virtuel, 6),
        exposition_max_dollars=round(exposition_max, 2) if exposition_max is not None else None,
        exposition_limitee=exposition_limitee,
    )
