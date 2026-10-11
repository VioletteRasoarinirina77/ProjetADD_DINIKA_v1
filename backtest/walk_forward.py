"""Backtesting walk-forward (D3).

Objectif :
    Valider si les signaux produits par indicators/technical.py (D2)
    sont réellement rentables de façon reproductible, avec coûts de
    transaction et sans fuite d'information du futur.

Méthodologie :
    - Découpage walk-forward en fenêtres [train][test].
    - Calibration du multiplicateur ATR uniquement sur train.
    - Application du paramètre calibré une seule fois sur test.
    - Décision sur le Close de la bougie t.
    - Entrée à l'Open de la bougie t+1.
    - Une seule position ouverte à la fois.
    - Stop-loss et take-profit calculés à l'entrée.
    - Coût de transaction basé sur spread_points de la configuration.

Métriques (décision D-009, figée) : Sharpe journalier annualisé par racine(252) et drawdown, tous deux
sur la courbe d'equity en dollars ; capital virtuel configurable, taille automatique (D-012).

Important :
    Des choix méthodologiques restent à valider par l'encadreur :
    - traitement d'une position encore ouverte à la fin d'une fenêtre ;
    - sémantique exacte du coût de transaction ;
    - grille de calibration du multiplicateur ATR.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest.equity import courbe_equity
from backtest.metrics import calculer_metriques
from backtest.simulator import simuler_trades
from config.instruments import obtenir_config, resoudre_capital_virtuel
from contracts.schemas import Bougie, ValidationBacktest
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe
from strategy.rules import generer_signaux_entree

# Noms réexportés : `simuler_trades`, `calculer_metriques` et `generer_signaux_entree`
# restent importables depuis ce module (utilisés par paper_trading/ et les tests).
__all__ = [
    "CANDIDATS_MULTIPLICATEUR_ATR",
    "calculer_metriques",
    "calibrer_multiplicateur_atr",
    "decouper_walk_forward",
    "generer_signaux_entree",
    "simuler_trades",
    "valider_parametres_backtest",
    "walk_forward_backtest",
]

# Choix méthodologique conservé pour la calibration D3.
# À valider par l'encadreur avant de le considérer comme définitif.
CANDIDATS_MULTIPLICATEUR_ATR = [1.5, 2.0, 2.5, 3.0]

# Organisation : la règle de signal vit dans strategy/rules.py, la simulation des trades
# dans backtest/simulator.py, les métriques dans backtest/metrics.py ; ce module
# orchestre uniquement le découpage walk-forward et la calibration sur TRAIN.


def decouper_walk_forward(
    df: pd.DataFrame,
    taille_train: int,
    taille_test: int,
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """Découpe la série en fenêtres walk-forward.

    Structure :

        [ TRAIN ][ TEST ]
               ↓
              avance de taille_test

        [ TRAIN ][ TEST ]

    La fenêtre est glissante et non ancrée.
    """
    fenetres: list[
        tuple[pd.DataFrame, pd.DataFrame]
    ] = []

    debut = 0

    while (
        debut + taille_train + taille_test
        <= len(df)
    ):
        train = df.iloc[
            debut : debut + taille_train
        ]

        test = df.iloc[
            debut + taille_train :
            debut + taille_train + taille_test
        ]

        fenetres.append(
            (train, test)
        )

        debut += taille_test

    return fenetres


def calibrer_multiplicateur_atr(
    train: pd.DataFrame,
    instrument_id: str,
    capital_virtuel: float,
) -> float:
    """Calibre le multiplicateur ATR-stop uniquement sur TRAIN.

    Pour chaque valeur candidate :
        1. simulation sur train ;
        2. calcul des métriques ;
        3. sélection de la valeur donnant le meilleur Sharpe.

    Le multiplicateur sélectionné est ensuite appliqué au TEST
    correspondant sans nouvelle calibration.

    La configuration globale de l'instrument n'est jamais modifiée.
    """
    meilleur_k = (
        obtenir_config(
            instrument_id
        ).risque.multiplicateur_atr_stop
    )

    meilleur_sharpe = -float("inf")
    multiplicateur = obtenir_config(instrument_id).multiplicateur_contrat

    
    signaux_train = generer_signaux_entree(train)

    for k_candidat in CANDIDATS_MULTIPLICATEUR_ATR:
        trades_candidat = simuler_trades(
            train,
            instrument_id,
            capital_virtuel,
            k_candidat,
            signaux_entree=signaux_train,
        )

        metriques_candidat = calculer_metriques(
            trades_candidat,
            courbe_equity(train, trades_candidat, capital_virtuel, multiplicateur),
        )

        if (
            metriques_candidat.sharpe is not None
            and metriques_candidat.sharpe
            > meilleur_sharpe
        ):
            meilleur_sharpe = (
                metriques_candidat.sharpe
            )
            meilleur_k = k_candidat

    return meilleur_k


def valider_parametres_backtest(
    taille_train: int,
    taille_test: int,
    capital_virtuel: float,
) -> None:
    """Vérifie les paramètres obligatoires du backtest."""
    if taille_train <= 0:
        raise ValueError(
            "taille_train doit être strictement positif."
        )

    if taille_test <= 0:
        raise ValueError(
            "taille_test doit être strictement positif."
        )

    if capital_virtuel <= 0:
        raise ValueError(
            "capital_virtuel doit être strictement positif."
        )


def walk_forward_backtest(
    bougies: list[Bougie],
    instrument_id: str,
    taille_train: int = 60,
    taille_test: int = 20,
    capital_virtuel: float | None = None,
) -> ValidationBacktest:
    """Point d'entrée principal du backtest walk-forward D3.

    Étapes :

        1. validation des paramètres ;
        2. conversion des bougies en DataFrame ;
        3. calcul des indicateurs D2 ;
        4. découpage en fenêtres TRAIN/TEST ;
        5. calibration du multiplicateur ATR sur TRAIN ;
        6. application du multiplicateur calibré sur TEST ;
        7. agrégation de tous les trades TEST ;
        8. calcul des métriques finales.

    Le résultat final provient uniquement des fenêtres TEST.
    """
    capital_virtuel = resoudre_capital_virtuel(instrument_id, capital_virtuel)
    valider_parametres_backtest(
        taille_train,
        taille_test,
        capital_virtuel,
    )

    df = ajouter_indicateurs(
        bougies_vers_dataframe(bougies),
        instrument_id,
    )

    fenetres = decouper_walk_forward(
        df,
        taille_train,
        taille_test,
    )

    if not fenetres:
        raise ValueError(
            f"Pas assez de bougies ({len(df)}) "
            f"pour au moins une fenêtre walk-forward "
            f"(train={taille_train} + "
            f"test={taille_test} = "
            f"{taille_train + taille_test} minimum)."
        )

    tous_les_trades: list[dict] = []
    multiplicateur = obtenir_config(instrument_id).multiplicateur_contrat
    capital_courant = float(capital_virtuel)
    morceaux_equity = [np.array([capital_courant])]

    for train, test in fenetres:
        # Calibration UNIQUEMENT sur TRAIN.
        k_calibre = calibrer_multiplicateur_atr(
            train,
            instrument_id,
            capital_courant,
        )

        # Application du paramètre calibré sur TEST.
        trades_test = simuler_trades(
            test,
            instrument_id,
            capital_courant,
            k_calibre,
        )
        equity_fenetre = courbe_equity(test, trades_test, capital_courant, multiplicateur)

        tous_les_trades.extend(
            trades_test
        )
        morceaux_equity.append(equity_fenetre[1:])
        # Les fenêtres TEST sont contiguës : le capital réalisé se reporte de l'une à l'autre.
        capital_courant = float(equity_fenetre[-1])

    return calculer_metriques(
        tous_les_trades,
        np.concatenate(morceaux_equity),
    )


if __name__ == "__main__":
    import json
    from pathlib import Path

    chemin = (
        Path(__file__).parent.parent
        / "fixtures"
        / "backtest/bougies_gold_150h.json"
    )

    with open(
        chemin,
        encoding="utf-8",
    ) as fichier:
        donnees = json.load(fichier)

    bougies = [
        Bougie(**donnee)
        for donnee in donnees
    ]

    resultat = walk_forward_backtest(
        bougies,
        "GOLD",
        taille_train=60,
        taille_test=20,
    )

    print(
        resultat.model_dump_json(
            indent=2
        )
    )
