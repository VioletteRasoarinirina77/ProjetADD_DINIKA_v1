"""Test dédié à la calibration réelle du multiplicateur ATR-stop sur 'train' (D3).

Complète tests/test_walk_forward.py (qui teste déjà la mécanique générale)
en vérifiant spécifiquement que calibrer_multiplicateur_atr() fait ce qu'elle
prétend : choisir, PARMI LES CANDIDATS, celui qui donne le meilleur Sharpe
SUR TRAIN — pas une valeur arbitraire ou toujours la même par défaut.
"""

import json
from pathlib import Path

from backtest.walk_forward import (
    CANDIDATS_MULTIPLICATEUR_ATR,
    ajouter_indicateurs,
    bougies_vers_dataframe,
    calculer_metriques,
    calibrer_multiplicateur_atr,
    decouper_walk_forward,
    simuler_trades,
)
from contracts.schemas import Bougie

FIXTURES_DIR = Path(__file__).parents[2] / "fixtures"


def charger_bougies(nom_fichier: str) -> list[Bougie]:
    with open(FIXTURES_DIR / "backtest" / nom_fichier, encoding="utf-8") as f:
        donnees = json.load(f)
    return [Bougie.model_validate(item) for item in donnees]


def test_calibrer_renvoie_bien_un_candidat_de_la_liste():
    bougies = charger_bougies("bougies_gold_300h.json")
    df = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    "GOLD",
)
    train = df.iloc[:60]

    k_calibre = calibrer_multiplicateur_atr(train, "GOLD", capital_virtuel=10_000.0)

    assert k_calibre in CANDIDATS_MULTIPLICATEUR_ATR




def test_calibrer_choisit_vraiment_le_meilleur_sharpe_sur_train():
    """Recalcule manuellement le Sharpe de chaque candidat sur la même fenêtre,
    et vérifie que calibrer_multiplicateur_atr() a bien choisi le meilleur —
    pas un test qui se contente de vérifier l'absence de crash."""
    bougies = charger_bougies("bougies_gold_300h.json")
    df = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    "GOLD",
)
    train = df.iloc[:60]

    k_calibre = calibrer_multiplicateur_atr(train, "GOLD", capital_virtuel=10_000.0)

    sharpes = {}
    for k in CANDIDATS_MULTIPLICATEUR_ATR:
        trades = simuler_trades(train, "GOLD", 10_000.0, k)
        metriques = calculer_metriques(trades)
        if metriques.sharpe is not None:
            sharpes[k] = metriques.sharpe

    if sharpes:  # si au moins un candidat a produit des trades sur cette fenêtre
        assert sharpes[k_calibre] == max(sharpes.values())


def test_walk_forward_backtest_calibre_une_fenetre_differente_a_chaque_iteration():
    """Preuve indirecte que train EST utilisé maintenant : deux fenêtres train
    différentes (données différentes) peuvent mener à des k calibrés différents
    -- ce test vérifie juste que calibrer_multiplicateur_atr() est appelable
    et cohérent sur 2 fenêtres réelles distinctes du même historique."""
    bougies = charger_bougies("bougies_gold_300h.json")
    df = ajouter_indicateurs(
    bougies_vers_dataframe(bougies),
    "GOLD",
)
    fenetres = decouper_walk_forward(df, taille_train=60, taille_test=20)

    assert len(fenetres) >= 2
    for train, _test in fenetres[:2]:
        k = calibrer_multiplicateur_atr(train, "GOLD", capital_virtuel=10_000.0)
        assert k in CANDIDATS_MULTIPLICATEUR_ATR
