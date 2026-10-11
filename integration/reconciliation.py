"""Réconciliation multi-sources.

Comble un trou entre le guide (partie 3, §3 "réconciliation multi-sources")
et le code réel : le guide décrivait la règle, mais rien ne l'appliquait
encore. Nécessaire dès que la Piste Data fournit plus d'une source pour un
même instrument (ex. COMEX en source primaire, OANDA en secours).

Règle rappelée : on ne moyenne JAMAIS deux sources. On les compare, et on
signale un écart anormal — sans bloquer le calcul, juste avec une alerte
explicite (donnée corrompue, mauvaise source, latence...).
"""

from pydantic import BaseModel

from contracts.schemas import Bougie


class AnomalieReconciliation(BaseModel):
    """Une ligne du rapport : un écart de prix trop grand entre 2 sources, au même instant."""

    instrument_id: str
    timestamp: str
    source_a: str
    close_a: float
    source_b: str
    close_b: float
    ecart_pct: float


def comparer_sources(
    bougies_source_a: list[Bougie],
    bougies_source_b: list[Bougie],
    tolerance_pct: float = 0.5,
) -> list[AnomalieReconciliation]:
    """Compare 2 séries de Bougies du MÊME instrument, provenant de 2 sources différentes.

    Ne compare que les instants communs aux deux séries (même timestamp exact) —
    des séries mal alignées dans le temps ne produiront simplement aucune comparaison
    sur les instants qui ne correspondent pas, plutôt qu'une fausse alerte.
    """
    index_b = {b.timestamp: b for b in bougies_source_b}
    anomalies: list[AnomalieReconciliation] = []

    for a in bougies_source_a:
        b = index_b.get(a.timestamp)
        if b is None:
            continue  # pas de donnée de l'autre source à cet instant précis, rien à comparer
        if a.instrument_id != b.instrument_id:
            continue  # garde-fou : ne jamais comparer 2 instruments différents par erreur

        ecart_pct = abs(a.close - b.close) / a.close * 100
        if ecart_pct > tolerance_pct:
            anomalies.append(
                AnomalieReconciliation(
                    instrument_id=a.instrument_id,
                    timestamp=a.timestamp.isoformat(),
                    source_a=a.source,
                    close_a=a.close,
                    source_b=b.source,
                    close_b=b.close,
                    ecart_pct=round(ecart_pct, 3),
                )
            )

    return anomalies
