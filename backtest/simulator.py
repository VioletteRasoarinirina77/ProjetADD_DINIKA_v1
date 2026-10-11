"""Simulation des trades D3.

Simule la stratégie de référence sur un DataFrame déjà enrichi des indicateurs D2.
Chaque trade porte son PnL en POINTS (`pnl_points`, indépendant de la taille : il mesure la
qualité du signal) ET en DOLLARS (`pnl_dollars` = points x multiplicateur x `taille`), la taille étant
dimensionnée automatiquement par D4 avec le capital COURANT (capital initial + PnL réalisés, décision
D-012). Les stops ne dépendent pas du capital : la séquence des trades est la même quel que soit le
capital, seule la taille change. La courbe d'equity et les métriques de risque en découlent
(`backtest/equity.py`, `backtest/metrics.py`, décision D-009).
"""

from __future__ import annotations

import pandas as pd

from config.instruments import obtenir_config, resoudre_capital_virtuel
from risk.position_sizing import calculer_risque
from strategy.rules import generer_signaux_entree

__all__ = ["generer_signaux_entree", "simuler_trades"]



def simuler_trades(
    df: pd.DataFrame,
    instrument_id: str,
    capital_virtuel: float | None = None,
    multiplicateur_atr_stop_override: float | None = None,
    signaux_entree: pd.Series | None = None,
) -> list[dict]:

    """Simule les trades sur un DataFrame déjà enrichi des indicateurs.

    Règles :
        - une seule position ouverte à la fois ;
        - position longue uniquement ;
        - entrée à l'Open de la bougie suivant le signal ;
        - SL/TP calculés une seule fois à l'entrée ;
        - coût de transaction appliqué à la sortie ;
        - si SL et TP sont touchés sur la même bougie, le SL est retenu
          comme hypothèse conservatrice.

    Remarque :
        Une position encore ouverte à la fin du DataFrame n'est pas
        ajoutée à la liste des trades. Ce choix doit être documenté
        et validé par l'encadreur.
    """
    
    entrees = (
generer_signaux_entree(df)
if signaux_entree is None
else signaux_entree
)

    config = obtenir_config(instrument_id)
    cout_transaction = config.spread_points
    multiplicateur_contrat = config.multiplicateur_contrat

    trades: list[dict] = []
    # Capital + PnL déjà réalisés : sert au dimensionnement de CHAQUE nouvelle entrée (D-012).
    capital_courant = resoudre_capital_virtuel(instrument_id, capital_virtuel)
    taille_position = 0

    en_position = False
    stop_loss: float | None = None
    take_profit: float | None = None
    prix_entree: float | None = None
    entree_ts = None

    # On s'arrête à len(df) - 1 car l'entrée d'un signal situé
    # sur la dernière bougie nécessiterait une bougie t+1.
    for i in range(len(df) - 1):
        ligne = df.iloc[i]
        ligne_suivante = df.iloc[i + 1]

        # ---------------------------------------------------------
        # Entrée
        # ---------------------------------------------------------
        if (
            not en_position
            and bool(entrees.iloc[i])
            and not pd.isna(ligne["atr_14"])
        ):
            prix_entree = float(ligne_suivante["open"])
            entree_ts = df.index[i + 1]

            # Dimensionné sur le capital COURANT (capital initial + PnL déjà réalisés), pas sur le
            # capital de départ figé : c'était le bug -- `capital_virtuel` (le paramètre d'entrée,
            # jamais mis à jour) était utilisé à la place de `capital_courant`, qui compte
            # `+= pnl_dollars` à chaque trade mais n'était en fait jamais lu (voir D-012).
            risque = calculer_risque(
                prix_entree,
                float(ligne["atr_14"]),
                instrument_id,
                capital_courant,
                multiplicateur_atr_stop_override=(
                    multiplicateur_atr_stop_override
                ),
            )

            stop_loss = risque.stop_loss
            take_profit = risque.take_profit
            taille_position = risque.taille_position_recommandee
            en_position = True

            # La bougie d'entrée t+1 n'est pas utilisée pour déterminer
            # immédiatement une sortie. Cette règle évite de supposer
            # un ordre intrabougie que les données OHLC ne permettent
            # pas de connaître précisément.
            continue

        # ---------------------------------------------------------
        # Gestion de la position
        # ---------------------------------------------------------
        if en_position:
            # Les valeurs ne peuvent pas être None ici puisque
            # en_position=True implique qu'elles ont été calculées
            # lors de l'entrée.
            assert stop_loss is not None
            assert take_profit is not None
            assert prix_entree is not None
            assert entree_ts is not None

            touche_stop = ligne_suivante["low"] <= stop_loss
            touche_profit = ligne_suivante["high"] >= take_profit

            if touche_stop or touche_profit:
                # Hypothèse conservatrice :
                # si SL et TP sont touchés sur la même bougie,
                # on retient le stop-loss.
                prix_sortie = (
                    stop_loss
                    if touche_stop
                    else take_profit
                )

                pnl_points = (
                    prix_sortie
                    - prix_entree
                    - cout_transaction
                )

                pnl_dollars = pnl_points * multiplicateur_contrat * taille_position
                capital_courant += pnl_dollars
                trades.append(
                    {
                        "entree_ts": entree_ts,
                        "sortie_ts": df.index[i + 1],
                        "prix_entree": prix_entree,
                        "prix_sortie": prix_sortie,
                        "pnl_points": pnl_points,
                        "taille": taille_position,
                        "pnl_dollars": pnl_dollars,
                    }
                )

                en_position = False
                stop_loss = None
                take_profit = None
                prix_entree = None
                entree_ts = None
                taille_position = 0

    return trades
