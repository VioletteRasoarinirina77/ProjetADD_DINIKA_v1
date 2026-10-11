"""Exposition maximale au niveau portefeuille.

Chaque trade individuel respecte déjà son propre % de risque (D4,
calculer_risque()). Ce module ajoute une limite d'exposition globale
lorsque plusieurs instruments sont simulés simultanément.

Le plafond d'exposition est exprimé comme un ratio du capital courant.

Exemple :
    capital = 10 000 $
    ratio = 3.0
    plafond = 30 000 $

Avant d'ouvrir une nouvelle position :

    exposition_existante + exposition_nouvelle <= plafond

Si le plafond serait dépassé, la position est refusée et le rejet
est enregistré dans trades_rejetes.

IMPORTANT :
    La valeur PLAFOND_EXPOSITION_RATIO_DEFAUT est une valeur technique
    provisoire. Sa validation métier doit être faite par l'encadreur.
"""

from datetime import datetime

import pandas as pd
from pydantic import BaseModel

from backtest.walk_forward import generer_signaux_entree
from config.instruments import obtenir_config
from contracts.schemas import Bougie
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from risk.position_sizing import calculer_risque

# Valeur provisoire à soumettre à validation de l'encadreur.
PLAFOND_EXPOSITION_RATIO_DEFAUT = 3.0


class TradeRejete(BaseModel):
    """Une position refusée par le plafond d'exposition."""

    instrument_id: str
    timestamp: datetime
    exposition_deja_engagee: float
    exposition_demandee: float
    plafond: float


class PositionOuverte(BaseModel):
    """Position actuellement ouverte dans le portefeuille."""

    instrument_id: str
    entree_ts: datetime
    prix_entree: float
    stop_loss: float
    take_profit: float
    taille_position: float
    exposition_dollars: float


class TradeFerme(BaseModel):
    """Trade fermé avec son résultat."""

    instrument_id: str
    entree_ts: datetime
    sortie_ts: datetime
    prix_entree: float
    prix_sortie: float
    taille_position: float
    pnl_dollars: float
    capital_apres: float


class ResultatPortefeuille(BaseModel):
    """Résultat complet de la simulation portefeuille."""

    capital_initial: float
    capital_final: float
    plafond_exposition_ratio: float
    trades: list[TradeFerme]
    trades_rejetes: list[TradeRejete]
    courbe_capital: list[float]


def simuler_portefeuille(
    bougies_par_instrument: dict[str, list[Bougie]],
    capital_initial: float = 10_000.0,
    plafond_exposition_ratio: float = PLAFOND_EXPOSITION_RATIO_DEFAUT,
) -> ResultatPortefeuille:
    """Simule plusieurs instruments en parallèle.

    Une nouvelle position est ouverte uniquement si :

        exposition_existante + exposition_nouvelle <= plafond

    Le plafond est calculé à partir du capital courant :

        plafond = capital * plafond_exposition_ratio
    """
    # ------------------------------------------------------------------
    # 0. Validation des paramètres
    # ------------------------------------------------------------------

    if capital_initial <= 0:
        raise ValueError(
            "capital_initial doit être strictement positif."
        )

    if plafond_exposition_ratio <= 0:
        raise ValueError(
            "plafond_exposition_ratio doit être strictement positif."
        )

    # ------------------------------------------------------------------
    # Cas sans instrument
    # ------------------------------------------------------------------

    if not bougies_par_instrument:
        return ResultatPortefeuille(
            capital_initial=capital_initial,
            capital_final=capital_initial,
            plafond_exposition_ratio=plafond_exposition_ratio,
            trades=[],
            trades_rejetes=[],
            courbe_capital=[capital_initial],
        )

    # ------------------------------------------------------------------
    # 1. Préparation des données
    # ------------------------------------------------------------------

    for instrument_id, bougies in bougies_par_instrument.items():
        if not bougies:
            raise ValueError(
                f"Aucune bougie fournie pour l'instrument {instrument_id}."
            )

    dfs = {
        instrument_id: ajouter_indicateurs(
            bougies_vers_dataframe(bougies),
            instrument_id,
        )
        for instrument_id, bougies in bougies_par_instrument.items()
    }

    signaux = {
        instrument_id: generer_signaux_entree(df)
        for instrument_id, df in dfs.items()
    }

    configs = {
        instrument_id: obtenir_config(instrument_id)
        for instrument_id in bougies_par_instrument
    }

    tous_les_timestamps = sorted(
        set().union(
            *(set(df.index) for df in dfs.values())
        )
    )

    capital = capital_initial
    courbe_capital = [capital]

    positions_ouvertes: dict[str, PositionOuverte] = {}
    trades: list[TradeFerme] = []
    trades_rejetes: list[TradeRejete] = []

    # ------------------------------------------------------------------
    # 2. Simulation chronologique
    # ------------------------------------------------------------------

    for ts in tous_les_timestamps:

        # ==============================================================
        # ÉTAPE A — sorties
        # ==============================================================

        for instrument_id in list(positions_ouvertes.keys()):

            df = dfs[instrument_id]

            if ts not in df.index:
                continue

            bougie = df.loc[ts]
            position = positions_ouvertes[instrument_id]

            touche_stop = bougie["low"] <= position.stop_loss
            touche_profit = bougie["high"] >= position.take_profit

            if not (touche_stop or touche_profit):
                continue

            # Convention conservatrice :
            # si SL et TP sont touchés dans la même bougie,
            # le Stop Loss est prioritaire.
            prix_sortie = (
                position.stop_loss
                if touche_stop
                else position.take_profit
            )

            config = configs[instrument_id]

            multiplicateur = config.multiplicateur_contrat
            cout_transaction = config.spread_points

            pnl_points = (
                prix_sortie
                - position.prix_entree
                - cout_transaction
            )

            pnl_dollars = (
                pnl_points
                * multiplicateur
                * position.taille_position
            )

            capital += pnl_dollars

            courbe_capital.append(capital)

            trades.append(
                TradeFerme(
                    instrument_id=instrument_id,
                    entree_ts=position.entree_ts,
                    sortie_ts=ts,
                    prix_entree=position.prix_entree,
                    prix_sortie=prix_sortie,
                    taille_position=position.taille_position,
                    pnl_dollars=round(pnl_dollars, 2),
                    capital_apres=round(capital, 2),
                )
            )

            del positions_ouvertes[instrument_id]

        # ==============================================================
        # ÉTAPE B — entrées
        # ==============================================================

        for instrument_id, df in dfs.items():

            # Une seule position simultanée par instrument.
            if instrument_id in positions_ouvertes:
                continue

            if ts not in df.index:
                continue

            position_index = df.index.get_loc(ts)

            if position_index == 0:
                continue

            # Le signal doit être généré sur la bougie précédente.
            ts_precedent = df.index[position_index - 1]

            if not bool(signaux[instrument_id].loc[ts_precedent]):
                continue

            atr_signal = df.loc[ts_precedent, "atr_14"]

            if pd.isna(atr_signal):
                continue

            prix_entree = float(df.loc[ts, "open"])

            risque = calculer_risque(
                prix_entree,
                float(atr_signal),
                instrument_id,
                capital,
            )

            taille = risque.taille_position_recommandee

            # Aucun contrat possible avec le risque disponible.
            if taille <= 0:
                continue

            config = configs[instrument_id]

            # ----------------------------------------------------------
            # Exposition de la nouvelle position
            # ----------------------------------------------------------

            exposition_nouvelle = (
                prix_entree
                * config.multiplicateur_contrat
                * taille
            )

            # ----------------------------------------------------------
            # Exposition déjà engagée
            # ----------------------------------------------------------

            exposition_deja_engagee = sum(
                position.exposition_dollars
                for position in positions_ouvertes.values()
            )

            # ----------------------------------------------------------
            # Plafond global
            # ----------------------------------------------------------

            plafond = capital * plafond_exposition_ratio

            exposition_totale = (
                exposition_deja_engagee
                + exposition_nouvelle
            )

            # ----------------------------------------------------------
            # REJET
            # ----------------------------------------------------------

            if exposition_totale > plafond:

                trades_rejetes.append(
                    TradeRejete(
                        instrument_id=instrument_id,
                        timestamp=ts,
                        exposition_deja_engagee=round(
                            exposition_deja_engagee,
                            2,
                        ),
                        exposition_demandee=round(
                            exposition_nouvelle,
                            2,
                        ),
                        plafond=round(
                            plafond,
                            2,
                        ),
                    )
                )

                continue

            # ----------------------------------------------------------
            # ACCEPTATION
            # ----------------------------------------------------------

            positions_ouvertes[instrument_id] = PositionOuverte(
                instrument_id=instrument_id,
                entree_ts=ts,
                prix_entree=prix_entree,
                stop_loss=risque.stop_loss,
                take_profit=risque.take_profit,
                taille_position=taille,
                exposition_dollars=round(
                    exposition_nouvelle,
                    2,
                ),
            )

    # ------------------------------------------------------------------
    # 3. Résultat
    # ------------------------------------------------------------------

    return ResultatPortefeuille(
        capital_initial=capital_initial,
        capital_final=round(capital, 2),
        plafond_exposition_ratio=plafond_exposition_ratio,
        trades=trades,
        trades_rejetes=trades_rejetes,
        courbe_capital=[
            round(valeur, 2)
            for valeur in courbe_capital
        ],
    )


if __name__ == "__main__":
    import json
    from pathlib import Path

    bougies_par_instrument = {}

    noms_fichiers = [
        ("GOLD", "backtest/bougies_gold_300h.json"),
        ("ES", "backtest/bougies_es_300h.json"),
    ]

    for instrument_id, nom_fichier in noms_fichiers:

        chemin = (
            Path(__file__).parent.parent
            / "fixtures"
            / nom_fichier
        )

        with open(chemin, encoding="utf-8") as fichier:
            donnees = json.load(fichier)

        bougies_par_instrument[instrument_id] = [
            Bougie(**donnee)
            for donnee in donnees
        ]

    resultat = simuler_portefeuille(
        bougies_par_instrument,
        plafond_exposition_ratio=3.0,
    )

    print(f"Trades exécutés : {len(resultat.trades)}")
    print(
        "Trades rejetés (plafond dépassé) : "
        f"{len(resultat.trades_rejetes)}"
    )
    print(f"Capital final : {resultat.capital_final}")
