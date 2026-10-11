"""Journal d'audit structuré (comble le CDC §5.2, non fonctionnel global : "journal d'audit").

Objectif : garder une trace horodatée, structurée (JSON) et exploitable
de chaque requête traitée par le service (main.py) et de la DÉCISION
renvoyée (le signal, ou le résultat de backtest lui-même) — pas seulement
"une requête est arrivée", mais "voici précisément ce qui a été répondu".

Pourquoi c'est important ici précisément : le principe directeur du projet
est "aide à la décision, jamais un décideur". Un journal d'audit est ce qui
permet de PROUVER après coup quel signal a été donné, quand, et sur quelle
base — plutôt que de devoir faire confiance sur parole. C'est aussi la
même logique que le "journal horodaté" déjà exigé pour D8 (paper-trading),
étendue ici à TOUT le service, pas seulement aux trades simulés.

Format : JSON Lines (1 objet JSON par ligne) dans logs/audit.jsonl — facile
à parser, agréger, ou charger dans un outil de supervision plus tard, sans
jamais changer le format existant (on ajoute des lignes, on n'en modifie
jamais).
"""

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

DOSSIER_LOGS = Path(__file__).parent.parent / "logs"
DOSSIER_LOGS.mkdir(exist_ok=True)
FICHIER_AUDIT = DOSSIER_LOGS / "audit.jsonl"


class FormateurJSON(logging.Formatter):
    """Convertit chaque enregistrement en une ligne JSON structurée, plutôt.

    qu'un message texte libre — un vrai journal d'audit doit être exploitable
    par un programme (recherche, agrégation), pas seulement lisible par un humain.
    """

    def format(self, enregistrement: logging.LogRecord) -> str:
        """Sérialise l'enregistrement de log en une ligne JSON (voir FormateurJSON)."""
        objet = {
            "timestamp": datetime.now(UTC).isoformat(),
            "niveau": enregistrement.levelname,
            "evenement": enregistrement.getMessage(),
        }
        objet.update(getattr(enregistrement, "champs_supplementaires", {}))
        return json.dumps(objet, ensure_ascii=False, default=str)


def _construire_logger() -> logging.Logger:
    logger = logging.getLogger("dinika.audit")
    logger.setLevel(logging.INFO)
    if logger.handlers:  # évite les handlers en double si le module est importé plusieurs fois
        return logger

    gestionnaire_fichier = logging.FileHandler(FICHIER_AUDIT, encoding="utf-8")
    gestionnaire_fichier.setFormatter(FormateurJSON())
    logger.addHandler(gestionnaire_fichier)

    gestionnaire_console = logging.StreamHandler(sys.stdout)
    gestionnaire_console.setFormatter(FormateurJSON())
    logger.addHandler(gestionnaire_console)

    logger.propagate = False  # évite les doublons via le logger racine
    return logger


logger_audit = _construire_logger()


def journaliser_requete(methode: str, chemin: str, statut_code: int, duree_ms: float) -> None:
    """Trace HTTP générique — une ligne par requête reçue par le service."""
    logger_audit.info(
        "requete_http",
        extra={
            "champs_supplementaires": {
                "type": "requete_http",
                "methode": methode,
                "chemin": chemin,
                "statut_code": statut_code,
                "duree_ms": round(duree_ms, 2),
            }
        },
    )


def journaliser_decision(type_decision: str, instrument_id: str, details: dict) -> None:
    """Trace la DÉCISION renvoyée par le système — pas seulement que la requête.

    a eu lieu, mais CE QUI a été répondu, pour l'explicabilité exigée par le CDC.
    """
    logger_audit.info(
        type_decision,
        extra={
            "champs_supplementaires": {
                "type": type_decision,
                "instrument_id": instrument_id,
                **details,
            }
        },
    )
