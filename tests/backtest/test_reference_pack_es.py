"""Valeurs de référence D3 sur le PACK ES gelé v1.0 (reproductibilité exigée par le CDC).

Ces valeurs proviennent du protocole corrigé : signal calculé sur la série continue (aucun faux
croisement au bord des fenêtres), sortie au Open en cas de gap sous le stop, Sharpe journalier
annualisé par racine(252), drawdown sur l'equity en dollars (D-009), capital 2 000 000 $ (D-012).
Elles NE démontrent PAS une stratégie rentable : le Sharpe est indiscernable de zéro.
Si ce test échoue après une modification, les chiffres du README et du rapport doivent être
régénérés (python -m scripts.generer_rapport_backtest) ET la modification expliquée.
"""

from pathlib import Path

import pytest

from backtest.walk_forward import walk_forward_backtest
from integration.pack_repository import PackDataRepository

PACK = Path(__file__).parents[2] / "fixtures" / "integration" / "pack_es_v1"


@pytest.fixture(scope="module")
def bougies_pack_es():
    """Les 4453 bougies du PACK, après vérification du SHA-256 par le repository."""
    return PackDataRepository(PACK).candles_validees("ES")


def test_walk_forward_250_60_sur_le_pack_es_reproduit_les_valeurs_de_reference(bougies_pack_es):
    assert len(bougies_pack_es) == 4453
    resultat = walk_forward_backtest(bougies_pack_es, "ES", taille_train=250, taille_test=60)

    assert resultat.nb_trades == 82
    assert resultat.taux_reussite == pytest.approx(0.341, abs=1e-3)
    assert resultat.sharpe == pytest.approx(0.019, abs=1e-3)
    assert resultat.drawdown_max == pytest.approx(0.178, abs=2e-3)