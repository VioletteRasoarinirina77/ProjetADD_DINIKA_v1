"""`backtest/simulator.py` et `backtest/metrics.py` portent désormais le code réel ;
`walk_forward.py` les réexporte : on vérifie l'identité des objets (compatibilité des imports)."""

from backtest import metrics, simulator, walk_forward
from strategy import rules


def test_walk_forward_reexporte_calculer_metriques_de_metrics():
    assert walk_forward.calculer_metriques is metrics.calculer_metriques


def test_walk_forward_reexporte_la_simulation_de_trades_de_simulator():
    assert walk_forward.simuler_trades is simulator.simuler_trades


def test_la_regle_de_signal_reste_unique_dans_strategy_rules():
    assert simulator.generer_signaux_entree is rules.generer_signaux_entree
    assert walk_forward.generer_signaux_entree is rules.generer_signaux_entree


def test_le_code_est_defini_dans_les_modules_cibles_pas_dans_walk_forward():
    assert simulator.simuler_trades.__module__ == "backtest.simulator"
    assert metrics.calculer_metriques.__module__ == "backtest.metrics"
