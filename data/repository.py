"""Accès aux données réelles via l'API HTTP de la Piste Data (mode production)."""

import os

import httpx

from contracts.schemas import Bougie


class DataRepository:
    """Accès aux données de la Piste DATA.

    La Piste Quant ne contacte pas directement Databento.
    Elle consomme uniquement l'API exposée par la Piste DATA.
    """

    def __init__(self, base_url: str | None = None):
        """Initialise le repository avec l'URL de la Piste DATA.

        Priorité :
        1. base_url fourni explicitement ;
        2. variable d'environnement PISTE_DATA_API_URL ;
        3. valeur par défaut http://localhost:8001.
        """
        self.base_url = (
            base_url
            or os.getenv(
                "PISTE_DATA_API_URL",
                "http://localhost:8001",
            )
        ).rstrip("/")

    def health(self) -> dict:
        """Vérifie que la Piste DATA est disponible."""
        response = httpx.get(
            f"{self.base_url}/health",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    def quality(self, instrument_id: str) -> dict:
        """Récupère le rapport de qualité des données."""
        response = httpx.get(
            f"{self.base_url}/api/v1/instruments/{instrument_id}/quality",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    def gaps(self, instrument_id: str) -> dict:
        """Récupère les informations sur les gaps."""
        response = httpx.get(
            f"{self.base_url}/api/v1/instruments/{instrument_id}/gaps",
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()

    def candles(self, instrument_id: str) -> list[Bougie]:
        """Récupère les bougies validées depuis la Piste DATA.

        Séquence obligatoire :
        health -> quality -> gaps -> candles
        """
        # 1. Vérification de disponibilité de la Piste DATA
        self.health()

        # 2. Vérification de la qualité des données
        quality = self.quality(instrument_id)

        if quality.get("valid") is False:
            raise ValueError(
                f"Données DATA invalides pour {instrument_id} : "
                f"{quality.get('errors', [])}"
            )

        # 3. Vérification des gaps
        self.gaps(instrument_id)

        # 4. Récupération des bougies
        response = httpx.get(
            f"{self.base_url}/api/v1/instruments/"
            f"{instrument_id}/candles",
            timeout=10.0,
        )
        response.raise_for_status()

        donnees = response.json()

        bougies = []

        for donnee in donnees:
            # Le pack DATA actuel est Daily.
            # Le contrat Bougie Quant exige un timeframe.
            donnee.setdefault("timeframe", "1D")

            bougies.append(Bougie(**donnee))

        # 5. Tri chronologique
        return sorted(
            bougies,
            key=lambda bougie: bougie.timestamp,
        )

    def candles_validees(self, instrument_id: str) -> list[Bougie]:
        """Point d'entrée utilisé par D2/D3/D4.

        Les données ne sont retournées que si la qualité
        déclarée par la Piste DATA est valide.
        """
        return self.candles(instrument_id)
