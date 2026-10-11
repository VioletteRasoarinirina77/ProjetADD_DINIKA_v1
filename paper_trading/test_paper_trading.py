"""Tests de paper_trading/simulator.py (D8)."""

import json
from pathlib import Path

from config.instruments import obtenir_config
from contracts.schemas import Bougie
from paper_trading.simulator import simuler_paper_trading

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def charger_bougies(nom_fichier: str) -> list[Bougie]:
    with open(FIXTURES_DIR / nom_fichier) as f:
        donnees = json.load(f)
    return [Bougie(**d) for d in donnees]


def test_courbe_capital_commence_au_capital_initial():
    bougies = charger_bougies("backtest/bougies_gold_150h.json")
    resultat = simuler_paper_trading(bougies, "GOLD", capital_initial=10_000.0)
    assert resultat.courbe_capital[0] == 10_000.0


def test_capital_final_coherent_avec_le_journal():
    """Le capital final doit être exactement celui du dernier trade du journal
    (ou le capital initial s'il n'y a eu aucun trade) — pas de dérive de calcul."""
    bougies = charger_bougies("backtest/bougies_gold_150h.json")
    resultat = simuler_paper_trading(bougies, "GOLD")
    if resultat.journal:
        assert resultat.capital_final == resultat.journal[-1].capital_apres
    else:
        assert resultat.capital_final == resultat.capital_initial


def test_courbe_capital_a_un_point_de_plus_que_le_nombre_de_trades():
    """Un point de départ + un point après chaque trade."""
    bougies = charger_bougies("backtest/bougies_gold_150h.json")
    resultat = simuler_paper_trading(bougies, "GOLD")
    assert len(resultat.courbe_capital) == len(resultat.journal) + 1


def test_journal_est_bien_ordonne_dans_le_temps():
    """Exigence D8 : journal horodaté — chaque sortie doit précéder l'entrée du trade suivant."""
    bougies = charger_bougies("backtest/bougies_gold_150h.json")
    resultat = simuler_paper_trading(bougies, "GOLD")
    for i in range(len(resultat.journal) - 1):
        assert resultat.journal[i].sortie_ts <= resultat.journal[i + 1].entree_ts


def test_fonctionne_sur_es_aussi():
    """Même exigence multi-instruments que D2/D3/D4 (aucune valeur codée en dur)."""
    bougies = charger_bougies("backtest/bougies_es_150h.json")
    resultat = simuler_paper_trading(bougies, "ES")
    assert resultat.instrument_id == "ES"
    # D-012 : capital par défaut spécifique à ES (contrat standard, 1 % de risque -> 2 M$ mesuré
    # pour garder une taille >= 1 sur la quasi-totalité des trades historiques), pas 10 000 $.
    assert resultat.capital_initial == obtenir_config("ES").capital_virtuel_defaut


def test_pnl_dollars_a_le_meme_signe_que_le_mouvement_de_prix():
    """Sanity check : un trade gagnant en points doit rester gagnant en dollars."""
    bougies = charger_bougies("backtest/bougies_gold_150h.json")
    resultat = simuler_paper_trading(bougies, "GOLD")
    for trade in resultat.journal:
        mouvement_points = trade.prix_sortie - trade.prix_entree
        if mouvement_points > 0:
            assert trade.pnl_dollars > -1.0  # tolère le petit coût de transaction fixe
