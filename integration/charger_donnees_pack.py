"""Chargeur du dataset du PACK ES Quant.

Lit directement le fichier CSV gelé du PACK et convertit
les lignes en objets Bougie.
"""

import csv
from pathlib import Path

from contracts.schemas import Bougie


def _valeur_ou_none(texte: str | None) -> float | None:
    """Convertit une valeur CSV vide en None sans inventer de valeur."""
    if texte is None or texte.strip() == "":
        return None

    return float(texte)


def charger_bougies_depuis_csv_pack(
    chemin_csv: str | Path,
    timeframe: str = "1D",
) -> list[Bougie]:
    """Charge le CSV du PACK et retourne une liste de Bougie."""
    bougies: list[Bougie] = []

    with open(chemin_csv, encoding="utf-8", newline="") as fichier:
        lecteur = csv.DictReader(fichier)

        for ligne in lecteur:
            bougies.append(
                Bougie(
                    instrument_id=ligne["instrument_id"],
                    source=ligne["source"],
                    timeframe=timeframe,
                    timestamp=ligne["timestamp"],
                    open=float(ligne["open"]),
                    high=float(ligne["high"]),
                    low=float(ligne["low"]),
                    close=float(ligne["close"]),
                    volume=float(ligne["volume"]),
                    open_interest=_valeur_ou_none(
                        ligne.get("open_interest")
                    ),
                    settlement_price=_valeur_ou_none(
                        ligne.get("settlement_price")
                    ),
                )
            )

    return bougies
