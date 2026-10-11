"""Tests de indicators/incremental.py.

Deux familles de tests :
1. Convergence : les valeurs incrémentales doivent se rapprocher du calcul
   batch (pandas-ta) une fois "chauffées" — avec une tolérance, pas une
   égalité stricte (l'amorçage diffère légèrement, voir le docstring du module).
2. Coût constant : la vraie raison d'être de ce module (exigence CDC < 5 s) —
   le temps de mettre_a_jour() ne doit PAS augmenter avec la taille de
   l'historique déjà vu.
"""

import json
import time
from pathlib import Path

import pytest

from contracts.schemas import Bougie
from indicators.incremental import EtatIndicateurs, mettre_a_jour
from indicators.technical import ajouter_indicateurs, bougies_vers_dataframe

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"


def charger_bougies_triees(nom_fichier: str) -> list[Bougie]:
    with open(
        FIXTURES_DIR / "backtest" / nom_fichier,
        encoding="utf-8",
    ) as f:
        donnees = json.load(f)
    return sorted([Bougie(**d) for d in donnees], key=lambda b: b.timestamp)


def rejouer_incremental(bougies: list[Bougie]) -> list:
    etat = EtatIndicateurs()
    indicateurs = []
    for b in bougies:
        etat, indic = mettre_a_jour(etat, b)
        indicateurs.append(indic)
    return indicateurs




def test_sma_20_est_identique_au_batch():
    """SMA = simple somme glissante -> aucune raison de différer, même pas d'un poil."""
    bougies = charger_bougies_triees("bougies_gold_150h.json")
    indics = rejouer_incremental(bougies)
    df_batch = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    "GOLD",
)

    for i in range(-10, 0):
        assert indics[i].sma_20 == pytest.approx(df_batch.iloc[i]["sma_20"], abs=1e-9)


def test_ema_20_converge_vers_le_batch():
    bougies = charger_bougies_triees("bougies_gold_150h.json")
    indics = rejouer_incremental(bougies)
    df_batch = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    "GOLD",
)

    for i in range(-10, 0):
        assert indics[i].ema_20 == pytest.approx(df_batch.iloc[i]["ema_20"], rel=1e-4)


def test_rsi_14_converge_vers_le_batch():
    bougies = charger_bougies_triees("bougies_gold_150h.json")
    indics = rejouer_incremental(bougies)
    df_batch = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    "GOLD",
)

    for i in range(-10, 0):
        assert indics[i].rsi_14 == pytest.approx(df_batch.iloc[i]["rsi_14"], abs=0.5)
        assert 0 <= indics[i].rsi_14 <= 100  # toujours borné, quelle que soit la méthode


def test_atr_14_converge_vers_le_batch():
    bougies = charger_bougies_triees("bougies_gold_150h.json")
    indics = rejouer_incremental(bougies)
    df_batch = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    "GOLD",
)

    for i in range(-10, 0):
        assert indics[i].atr_14 == pytest.approx(df_batch.iloc[i]["atr_14"], rel=1e-3)


def test_macd_converge_vers_le_batch():
    """Tolérance plus large ici : le MACD combine 3 EMA emboîtées (12, 26, 9),
    donc les petits écarts d'amorçage s'accumulent un peu plus qu'ailleurs."""
    bougies = charger_bougies_triees("bougies_gold_150h.json")
    indics = rejouer_incremental(bougies)
    df_batch = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    "GOLD",
)

    for i in range(-10, 0):
        assert indics[i].macd == pytest.approx(df_batch.iloc[i]["macd"], abs=0.01)


def test_indicateurs_absents_pendant_la_periode_de_chauffe():
    """Avec seulement 5 bougies, aucun indicateur ne doit être disponible (None) --
    même comportement attendu que la version batch (technical.py)."""
    bougies = charger_bougies_triees("bougies_gold_150h.json")[:5]
    indics = rejouer_incremental(bougies)
    dernier = indics[-1]
    assert dernier.sma_20 is None
    assert dernier.rsi_14 is None
    assert dernier.atr_14 is None


def test_cout_de_mise_a_jour_est_constant_pas_croissant():
    """LE test qui justifie ce module entier (exigence CDC "< 5 s") : le temps
    de traiter la bougie n°1000 ne doit pas être plus long que celui de la
    bougie n°10 -- sinon on n'a rien gagné par rapport au recalcul complet."""
    bougies_courtes = charger_bougies_triees("bougies_gold_150h.json")[:30]
    bougies_longues = charger_bougies_triees("bougies_gold_150h.json")  # 150 bougies

    etat = EtatIndicateurs()
    for b in bougies_courtes[:-1]:
        etat, _ = mettre_a_jour(etat, b)
    debut = time.perf_counter()
    for _ in range(200):  # répété pour une mesure stable, une seule bougie coûte trop peu de temps
        mettre_a_jour(etat, bougies_courtes[-1])
    duree_apres_30 = time.perf_counter() - debut

    etat = EtatIndicateurs()
    for b in bougies_longues[:-1]:
        etat, _ = mettre_a_jour(etat, b)
    debut = time.perf_counter()
    for _ in range(200):
        mettre_a_jour(etat, bougies_longues[-1])
    duree_apres_150 = time.perf_counter() - debut

    # Tolérance large (x3) : on ne cherche pas une égalité parfaite (bruit de mesure),
    # seulement l'ABSENCE d'une croissance proportionnelle à l'historique (qui donnerait x5).
    assert duree_apres_150 < duree_apres_30 * 3


def test_fonctionne_aussi_sur_es():
    """Même exigence multi-instruments que le reste du projet."""
    bougies = charger_bougies_triees("bougies_es_150h.json")
    indics = rejouer_incremental(bougies)
    assert indics[-1].sma_20 is not None
    assert indics[-1].atr_14 is not None
