"""Alertes du panneau Risque/Quant (D7) — logique pure, sans Streamlit.

Critère CDC (D7, voir le prompt RTFC) : "synthèse < 3 s ; alertes < 5 s ; bandeau d'avertissement
permanent". `dashboard/synthese.py` couvre la synthèse et le bandeau ; ce module couvre les alertes,
avec son propre chronométrage, mesuré par test (`SEUIL_ALERTE_SECONDES`).

Une alerte signale un état qui mérite l'attention immédiate de l'utilisateur -- pas seulement une
information de contexte déjà visible ailleurs dans le panneau (l'origine des données, par exemple,
reste dans `SynthesePanneauRisque.libelle_origine`, pas ici).
"""

from __future__ import annotations

import time
from enum import StrEnum

from pydantic import BaseModel

from config.instruments import obtenir_config
from dashboard.synthese import SynthesePanneauRisque
from integration.reconciliation import AnomalieReconciliation

SEUIL_ALERTE_SECONDES = 5.0  # critère CDC D7

# Seuils d'alerte : valeurs de travail, à valider par l'encadreur (comme les autres seuils du
# projet -- voir docs/decisions.md). Choisis pour signaler un état concret sans noyer l'utilisateur
# sous des alertes triviales : un drawdown de 50 % ou un Sharpe très négatif méritent d'être vus.
SEUIL_DRAWDOWN_AVERTISSEMENT = 0.30
SEUIL_DRAWDOWN_CRITIQUE = 0.50
SEUIL_SHARPE_NEGATIF = -1.0
NB_TRADES_MINIMUM_FIABLE = 20


class NiveauAlerte(StrEnum):
    """Sévérité d'une alerte, du simple rappel au signal bloquant pour la décision."""

    INFO = "info"
    AVERTISSEMENT = "avertissement"
    CRITIQUE = "critique"


class Alerte(BaseModel):
    """Une alerte affichable telle quelle dans le panneau."""

    niveau: NiveauAlerte
    code: str
    message: str


def _alerte_taille_nulle(synthese: SynthesePanneauRisque) -> Alerte | None:
    if synthese.explication_taille_nulle is None:
        return None
    return Alerte(
        niveau=NiveauAlerte.AVERTISSEMENT,
        code="taille_position_nulle",
        message=synthese.explication_taille_nulle,
    )


def _alerte_drawdown(synthese: SynthesePanneauRisque) -> Alerte | None:
    if synthese.drawdown_max is None:
        return None
    if synthese.drawdown_max >= SEUIL_DRAWDOWN_CRITIQUE:
        niveau = NiveauAlerte.CRITIQUE
    elif synthese.drawdown_max >= SEUIL_DRAWDOWN_AVERTISSEMENT:
        niveau = NiveauAlerte.AVERTISSEMENT
    else:
        return None
    return Alerte(
        niveau=niveau,
        code="drawdown_eleve",
        message=(
            f"Drawdown maximum de {synthese.drawdown_max:.1%} sur la période de validation walk-forward "
            f"({synthese.nb_trades} trades) : la stratégie de référence a connu une perte importante "
            f"avant de s'en remettre. Ce n'est pas une promesse de gain (voir le bandeau)."
        ),
    )


def _alerte_sharpe_negatif(synthese: SynthesePanneauRisque) -> Alerte | None:
    if synthese.sharpe is None or synthese.sharpe >= SEUIL_SHARPE_NEGATIF:
        return None
    return Alerte(
        niveau=NiveauAlerte.AVERTISSEMENT,
        code="sharpe_negatif",
        message=(
            f"Sharpe annualisé fortement négatif ({synthese.sharpe:.2f}) sur la période de validation : "
            f"la stratégie de référence a perdu de l'argent de façon régulière, pas seulement "
            f"ponctuellement."
        ),
    )


def _alerte_peu_de_trades(synthese: SynthesePanneauRisque) -> Alerte | None:
    if synthese.nb_trades == 0:
        return Alerte(
            niveau=NiveauAlerte.AVERTISSEMENT,
            code="aucun_trade",
            message=(
                "Aucun trade sur la période de validation walk-forward : les métriques (Sharpe, "
                "drawdown, taux de réussite) ne peuvent pas être calculées."
            ),
        )
    if synthese.nb_trades < NB_TRADES_MINIMUM_FIABLE:
        return Alerte(
            niveau=NiveauAlerte.INFO,
            code="peu_de_trades",
            message=(
                f"Seulement {synthese.nb_trades} trades sur la période de validation : les métriques "
                f"restent peu fiables statistiquement en dessous de {NB_TRADES_MINIMUM_FIABLE}."
            ),
        )
    return None


def _alerte_atr_indisponible(synthese: SynthesePanneauRisque) -> Alerte | None:
    if synthese.signal.indicateurs.atr_14 is not None:
        return None
    return Alerte(
        niveau=NiveauAlerte.AVERTISSEMENT,
        code="atr_indisponible",
        message=(
            f"ATR indisponible pour {synthese.instrument_id} : l'historique fourni est trop court pour "
            f"chauffer l'indicateur (voir config.instruments.ParametresIndicateurs.periode_atr). Aucun "
            f"stop, take-profit ni taille de position ne peut être calculé tant que ce n'est pas résolu."
        ),
    )


def _alertes_reconciliation(anomalies: list[AnomalieReconciliation]) -> list[Alerte]:
    return [
        Alerte(
            niveau=NiveauAlerte.CRITIQUE if abs(a.ecart_pct) >= 5.0 else NiveauAlerte.AVERTISSEMENT,
            code="ecart_reconciliation",
            message=(
                f"{a.instrument_id} à {a.timestamp} : écart de {a.ecart_pct:.2f} % entre {a.source_a} "
                f"({a.close_a}) et {a.source_b} ({a.close_b}). Vérifier la source avant de faire "
                f"confiance au signal."
            ),
        )
        for a in anomalies
    ]


def generer_alertes(
    synthese: SynthesePanneauRisque,
    anomalies_reconciliation: list[AnomalieReconciliation] | None = None,
) -> tuple[list[Alerte], float]:
    """Calcule les alertes du panneau et le temps mis pour le faire (critère CDC : < 5 s).

    Ne relit ni ne recalcule rien de coûteux : part de la `SynthesePanneauRisque` déjà produite
    (< 3 s, critère séparé) et d'éventuelles anomalies de réconciliation déjà détectées. Un
    consommateur de ce module n'a donc jamais à choisir entre respecter le seuil de 3 s de la
    synthèse et celui de 5 s des alertes : les deux se cumulent naturellement sous 5 s.
    """
    debut = time.perf_counter()
    obtenir_config(synthese.instrument_id)  # lève KeyError si l'instrument est inconnu

    candidates = [
        _alerte_atr_indisponible(synthese),
        _alerte_taille_nulle(synthese),
        _alerte_peu_de_trades(synthese),
        _alerte_sharpe_negatif(synthese),
        _alerte_drawdown(synthese),
    ]
    alertes = [a for a in candidates if a is not None]
    alertes.extend(_alertes_reconciliation(anomalies_reconciliation or []))

    ordre = {NiveauAlerte.CRITIQUE: 0, NiveauAlerte.AVERTISSEMENT: 1, NiveauAlerte.INFO: 2}
    alertes.sort(key=lambda a: ordre[a.niveau])

    return alertes, round(time.perf_counter() - debut, 4)
