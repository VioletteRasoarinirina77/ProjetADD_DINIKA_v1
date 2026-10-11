"""Service FastAPI — Piste Quant (D2/D3/D4).

Expose calculer_signal_quantitatif() (D2+D4) et walk_forward_backtest() (D3)
via une API HTTP, pour que la Piste IA (D6) et le tableau de bord (D7)
puissent les consommer sans dépendre du langage/environnement de qui les appelle.

MISE À JOUR :
- Calcul incrémental réellement branché.
- L'accès à l'API de la Piste DATA est centralisé dans DataRepository.
- main.py ne contacte plus directement l'API DATA.
- En production, les données passent par DataRepository :
  health -> quality -> gaps -> candles.

Source des Bougies (voir obtenir_bougies()) :
- ENVIRONMENT=prod : API de la Piste DATA via DataRepository (tous instruments).
- Tout autre environnement (dev, pack, ou absent) :
  - instrument REEL_GELE (ES) : exclusivement le pack gelé DINIKA_ES_QUANT_PACK,
    vérifié par SHA-256 -- jamais de fixture pour un instrument qui dispose de
    données réelles, quel que soit l'environnement.
  - instrument SYNTHETIQUE (GOLD, aucun pack réel n'existe) : fixtures locales,
    toujours présentées comme synthétiques.
"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from audit.logger import journaliser_decision, journaliser_requete
from backtest.walk_forward import walk_forward_backtest
from config.instruments import (
    INSTRUMENTS,
    OrigineDonnees,
    obtenir_config,
    resoudre_capital_portefeuille,
)
from contracts.schemas import Bougie, SignalQuantitatif, ValidationBacktest
from data.repository import DataRepository
from indicators.incremental import EtatIndicateurs, mettre_a_jour
from integration.pack_repository import ErreurIntegritePack, PackDataRepository
from integration.reconciliation import AnomalieReconciliation, comparer_sources
from paper_trading.portfolio import (
    PLAFOND_EXPOSITION_RATIO_DEFAUT,
    ResultatPortefeuille,
    simuler_portefeuille,
)
from risk.position_sizing import calculer_risque

load_dotenv()

app = FastAPI(
    title="DINIKA — Piste Quant",
    description=(
        "Indicateurs techniques (D2), backtesting walk-forward (D3) "
        "et gestion du risque (D4)."
    ),
    version="0.1.0",
)


@app.middleware("http")
async def middleware_journal_audit(request: Request, call_next):
    """Trace chaque requête reçue par le service.

    Journalise :
    - méthode HTTP ;
    - chemin ;
    - code de statut ;
    - durée d'exécution.

    Répond à l'exigence de journal d'audit du projet.
    """
    debut = time.perf_counter()

    reponse = await call_next(request)

    duree_ms = (time.perf_counter() - debut) * 1000

    journaliser_requete(
        request.method,
        request.url.path,
        reponse.status_code,
        duree_ms,
    )

    return reponse


FIXTURES_DIR = Path(__file__).parent / "fixtures"

FIXTURES_PAR_INSTRUMENT = {
    "GOLD": "backtest/bougies_gold_150h.json",
    "ES": "backtest/bougies_es_150h.json",
}


# ---------------------------------------------------------------------------
# ACCÈS AUX DONNÉES
# ---------------------------------------------------------------------------

def obtenir_bougies_depuis_fixtures(instrument_id: str) -> list[Bougie]:
    """Source de secours pour le développement local.

    Les fixtures permettent de travailler sans dépendre de la disponibilité
    de l'API de la Piste DATA.
    """
    nom_fichier = FIXTURES_PAR_INSTRUMENT.get(instrument_id)

    if nom_fichier is None:
        raise HTTPException(
            status_code=404,
            detail=f"Pas de fixture pour {instrument_id}.",
        )

    chemin_fichier = FIXTURES_DIR / nom_fichier

    try:
        with open(chemin_fichier, encoding="utf-8") as fichier:
            donnees = json.load(fichier)
    except FileNotFoundError as erreur:
        raise HTTPException(
            status_code=404,
            detail=f"Fixture introuvable pour {instrument_id}.",
        ) from erreur
    except json.JSONDecodeError as erreur:
        raise HTTPException(
            status_code=500,
            detail=f"Fixture invalide pour {instrument_id}.",
        ) from erreur

    return [Bougie(**donnee) for donnee in donnees]


# Instance unique du repository.
# Le repository centralise désormais tous les appels vers la Piste DATA.
def _creer_repository_data() -> DataRepository:
    """Crée le repository DATA avec la configuration courante."""
    return DataRepository()


def obtenir_bougies_via_api(instrument_id: str) -> list[Bougie]:
    """Récupère les données validées depuis la Piste DATA."""
    repository_data = _creer_repository_data()

    try:
        return repository_data.candles_validees(instrument_id)

    except ValueError as erreur:
        raise HTTPException(
            status_code=502,
            detail=str(erreur),
        ) from erreur

    except Exception as erreur:
        raise HTTPException(
            status_code=503,
            detail=(
                f"API de la Piste DATA indisponible pour "
                f"{instrument_id} : {erreur}"
            ),
        ) from erreur




PACK_DIR_DEFAUT = FIXTURES_DIR / "integration" / "pack_es_v1"


def _creer_repository_pack() -> PackDataRepository:
    """Repository sur le pack gelé livré par la Piste Data (SHA-256 vérifié).

    Dossier configurable par DINIKA_PACK_DIR, sinon le pack versionné du dépôt.
    """
    return PackDataRepository(os.getenv("DINIKA_PACK_DIR", str(PACK_DIR_DEFAUT)))


def _instrument_est_reel(instrument_id: str) -> bool:
    return obtenir_config(instrument_id).origine_donnees is OrigineDonnees.REEL_GELE


def obtenir_bougies(instrument_id: str) -> list[Bougie]:
    """Point d'entrée unique pour récupérer les bougies.

    - prod : DataRepository -> API Piste DATA (la seule source "live") ;
    - tout autre environnement (dev, pack, ou absent), pour un instrument
      REEL_GELE (ES) : le pack gelé DINIKA_ES_QUANT_PACK est la SEULE source
      de données marché, vérifiée par SHA-256 -- jamais de fixture pour un
      instrument qui dispose de données réelles. Aucune valeur de marché
      inventée ou externe n'entre dans D2/D3/D4 pour cet instrument ;
    - instrument SYNTHETIQUE (GOLD) : aucun pack réel n'existe -> fixtures,
      toujours présentées comme synthétiques (voir /provenance), jamais
      confondues avec une donnée réelle.
    """
    environnement = os.getenv("ENVIRONMENT", "dev").lower()

    if environnement == "prod":
        return obtenir_bougies_via_api(instrument_id)

    if instrument_id in INSTRUMENTS and _instrument_est_reel(instrument_id):
        try:
            return _creer_repository_pack().candles_validees(instrument_id)
        except (ErreurIntegritePack, ValueError, FileNotFoundError) as erreur:
            raise HTTPException(
                status_code=503,
                detail=f"Pack de données inutilisable pour {instrument_id} : {erreur}",
            ) from erreur

    return obtenir_bougies_depuis_fixtures(instrument_id)


def _provenance_donnees(instrument_id: str) -> dict:
    """Origine des données RÉELLEMENT utilisées pour un résultat (traçabilité).

    Doit toujours rester le miroir exact de obtenir_bougies() : annoncer une
    origine qui ne correspond pas aux données effectivement chargées induirait
    le journal d'audit et les consommateurs de /provenance en erreur.

    - prod : API de la Piste Data -> origine de la config, sans hash (le service DATA n'en fournit pas) ;
    - tout autre environnement (dev, pack, ou absent), instrument REEL_GELE (ES) :
      obtenir_bougies() lit exclusivement le pack gelé -> origine de la config
      (réel gelé) + version + hash du pack ;
    - instrument SYNTHETIQUE (GOLD) : fixtures -> toujours synthétique, sans hash.
    """
    environnement = os.getenv("ENVIRONMENT", "dev").lower()
    if environnement != "prod" and _instrument_est_reel(instrument_id):
        origine = obtenir_config(instrument_id).origine_donnees.value
        return {"origine_donnees": origine, **_creer_repository_pack().provenance()}
    if environnement == "prod":
        origine = obtenir_config(instrument_id).origine_donnees.value
    else:
        origine = OrigineDonnees.SYNTHETIQUE.value
    return {"origine_donnees": origine, "dataset_version": None, "sha256": None}


# ---------------------------------------------------------------------------
# ÉTAT INCRÉMENTAL
# ---------------------------------------------------------------------------

_etats_indicateurs: dict[str, EtatIndicateurs] = {}
_dernier_signal: dict[str, SignalQuantitatif] = {}


def _etat_ou_chauffer(instrument_id: str) -> EtatIndicateurs:
    """Renvoie l'état incrémental de l'instrument.

    Lors du premier appel :
    - récupération de l'historique ;
    - tri chronologique ;
    - chauffage de l'état incrémental.

    Les appels suivants réutilisent l'état conservé en mémoire.
    """
    if instrument_id not in _etats_indicateurs:
        bougies_historiques = sorted(
            obtenir_bougies(instrument_id),
            key=lambda b: b.timestamp,
        )

        if not bougies_historiques:
            raise ValueError(
                f"Aucune bougie disponible pour {instrument_id}."
            )

        etat = EtatIndicateurs()
        indicateurs = None

        for bougie in bougies_historiques:
            etat, indicateurs = mettre_a_jour(
                etat,
                bougie,
            )

        if indicateurs is None:
            raise ValueError(
                f"Impossible de calculer les indicateurs pour {instrument_id}."
            )

        _etats_indicateurs[instrument_id] = etat

        derniere_bougie = bougies_historiques[-1]

        risque = calculer_risque(
            derniere_bougie.close,
            indicateurs.atr_14,
            instrument_id,
        )

        _dernier_signal[instrument_id] = SignalQuantitatif(
            instrument_id=derniere_bougie.instrument_id,
            source=derniere_bougie.source,
            timeframe=derniere_bougie.timeframe,
            timestamp=derniere_bougie.timestamp,
            indicateurs=indicateurs,
            risque=risque,
            validation=None,
        )

    return _etats_indicateurs[instrument_id]


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    """Sonde de disponibilité : liste les instruments configurés, sans dépendre des données."""
    return {
        "statut": "ok",
        "instruments_configures": list(INSTRUMENTS.keys()),
    }


# ---------------------------------------------------------------------------
# D2 + D4 : SIGNAL QUANTITATIF
# ---------------------------------------------------------------------------

@app.get(
    "/signal/{instrument_id}",
    response_model=SignalQuantitatif,
)
def obtenir_signal(instrument_id: str) -> SignalQuantitatif:
    """Retourne le dernier signal quantitatif.

    Utilisé notamment par :
    - Piste IA D6 ;
    - tableau de bord D7.

    Après le premier chauffage, le calcul incrémental est réutilisé.
    """
    if instrument_id not in INSTRUMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Instrument inconnu : {instrument_id}",
        )

    try:
        _etat_ou_chauffer(instrument_id)

    except HTTPException:
        raise

    except (ValueError, KeyError) as erreur:
        raise HTTPException(
            status_code=422,
            detail=str(erreur),
        ) from erreur

    signal = _dernier_signal[instrument_id]

    journaliser_decision(
        "signal_quantitatif",
        instrument_id,
        {
            "rsi_14": signal.indicateurs.rsi_14,
            "atr_14": signal.indicateurs.atr_14,
            "stop_loss": signal.risque.stop_loss,
            "take_profit": signal.risque.take_profit,
            "taille_position_recommandee": (
                signal.risque.taille_position_recommandee
            ),
        },
    )

    return signal


# ---------------------------------------------------------------------------
# NOUVELLE BOUGIE : CALCUL INCRÉMENTAL
# ---------------------------------------------------------------------------

@app.post(
    "/bougie/{instrument_id}",
    response_model=SignalQuantitatif,
)
def ingerer_bougie(
    instrument_id: str,
    nouvelle_bougie: Bougie,
) -> SignalQuantitatif:
    """Injecte une nouvelle bougie et met à jour les indicateurs.

    Le calcul utilise uniquement l'état incrémental déjà présent en mémoire.
    L'historique n'est donc pas retraité après le chauffage initial.
    """
    if instrument_id not in INSTRUMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Instrument inconnu : {instrument_id}",
        )

    if nouvelle_bougie.instrument_id != instrument_id:
        raise HTTPException(
            status_code=422,
            detail=(
                f"instrument_id du chemin ({instrument_id}) et du corps "
                f"({nouvelle_bougie.instrument_id}) ne correspondent pas."
            ),
        )

    try:
        etat_actuel = _etat_ou_chauffer(instrument_id)

        nouvel_etat, indicateurs = mettre_a_jour(
            etat_actuel,
            nouvelle_bougie,
        )

        _etats_indicateurs[instrument_id] = nouvel_etat

        risque = calculer_risque(
            nouvelle_bougie.close,
            indicateurs.atr_14,
            instrument_id,
        )

    except HTTPException:
        raise

    except (ValueError, KeyError) as erreur:
        raise HTTPException(
            status_code=422,
            detail=str(erreur),
        ) from erreur

    signal = SignalQuantitatif(
        instrument_id=nouvelle_bougie.instrument_id,
        source=nouvelle_bougie.source,
        timeframe=nouvelle_bougie.timeframe,
        timestamp=nouvelle_bougie.timestamp,
        indicateurs=indicateurs,
        risque=risque,
        validation=None,
    )

    _dernier_signal[instrument_id] = signal

    journaliser_decision(
        "bougie_ingeree",
        instrument_id,
        {
            "timestamp_bougie": nouvelle_bougie.timestamp,
            "close": nouvelle_bougie.close,
            "rsi_14": signal.indicateurs.rsi_14,
            "atr_14": signal.indicateurs.atr_14,
        },
    )

    return signal


# ---------------------------------------------------------------------------
# D3 : WALK-FORWARD BACKTEST
# ---------------------------------------------------------------------------

@app.get(
    "/backtest/{instrument_id}",
    response_model=ValidationBacktest,
)
def obtenir_backtest(
    instrument_id: str,
    taille_train: int = 60,
    taille_test: int = 20,
    capital_virtuel: float | None = None,
) -> ValidationBacktest:
    """Exécute le backtest walk-forward sur les données disponibles.

    `capital_virtuel` : facultatif (défaut : configuration de l'instrument ou DINIKA_CAPITAL_VIRTUEL, D-012).
    """
    if instrument_id not in INSTRUMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Instrument inconnu : {instrument_id}",
        )

    try:
        bougies = obtenir_bougies(instrument_id)

        resultat = walk_forward_backtest(
            bougies,
            instrument_id,
            taille_train,
            taille_test,
            capital_virtuel,
        )

    except HTTPException:
        raise

    except ValueError as erreur:
        raise HTTPException(
            status_code=422,
            detail=str(erreur),
        ) from erreur

    journaliser_decision(
        "validation_backtest",
        instrument_id,
        {
            "sharpe": resultat.sharpe,
            "drawdown_max": resultat.drawdown_max,
            "taux_reussite": resultat.taux_reussite,
            "nb_trades": resultat.nb_trades,
            "taille_train": taille_train,
            "taille_test": taille_test,
            **_provenance_donnees(instrument_id),
        },
    )

    return resultat


@app.get("/provenance/{instrument_id}")
def obtenir_provenance(instrument_id: str) -> dict:
    """Version du dataset et SHA-256 utilisés pour les résultats d'un instrument.

    Un instrument synthétique renvoie origine_donnees='synthetique' et aucun hash.
    """
    if instrument_id not in INSTRUMENTS:
        raise HTTPException(status_code=404, detail=f"Instrument inconnu : {instrument_id}")
    try:
        return _provenance_donnees(instrument_id)
    except ErreurIntegritePack as erreur:
        raise HTTPException(status_code=503, detail=str(erreur)) from erreur


# ---------------------------------------------------------------------------
# D4 / D7 : PORTEFEUILLE
# ---------------------------------------------------------------------------

@app.get(
    "/portefeuille",
    response_model=ResultatPortefeuille,
)
def obtenir_portefeuille(
    instruments: str = ",".join(INSTRUMENTS.keys()),
    capital_initial: float | None = None,
    plafond_exposition_ratio: float = PLAFOND_EXPOSITION_RATIO_DEFAUT,
) -> ResultatPortefeuille:
    """Simule les instruments demandés avec un plafond d'exposition partagé.

    Exemple :
        /portefeuille?instruments=GOLD,ES
    """
    instrument_ids = [
        instrument.strip()
        for instrument in instruments.split(",")
        if instrument.strip()
    ]

    inconnus = [
        instrument
        for instrument in instrument_ids
        if instrument not in INSTRUMENTS
    ]

    if inconnus:
        raise HTTPException(
            status_code=404,
            detail=f"Instrument(s) inconnu(s) : {inconnus}",
        )

    capital_initial = resoudre_capital_portefeuille(instrument_ids, capital_initial)

    try:
        bougies_par_instrument = {
            instrument_id: obtenir_bougies(instrument_id)
            for instrument_id in instrument_ids
        }

        resultat = simuler_portefeuille(
            bougies_par_instrument,
            capital_initial,
            plafond_exposition_ratio,
        )

    except HTTPException:
        raise

    except ValueError as erreur:
        raise HTTPException(
            status_code=422,
            detail=str(erreur),
        ) from erreur

    journaliser_decision(
        "validation_portefeuille",
        ",".join(instrument_ids),
        {
            "capital_final": resultat.capital_final,
            "nb_trades": len(resultat.trades),
            "nb_trades_rejetes": len(resultat.trades_rejetes),
            "plafond_exposition_ratio": plafond_exposition_ratio,
        },
    )

    return resultat


# ---------------------------------------------------------------------------
# RÉCONCILIATION
# ---------------------------------------------------------------------------

class DemandeReconciliation(BaseModel):
    """Corps de POST /reconciliation : deux séries de Bougies du même instrument à comparer."""

    bougies_source_a: list[Bougie]
    bougies_source_b: list[Bougie]


@app.post(
    "/reconciliation",
    response_model=list[AnomalieReconciliation],
)
def verifier_reconciliation(
    demande: DemandeReconciliation,
    tolerance_pct: float = 0.5,
) -> list[AnomalieReconciliation]:
    """Compare deux séries de bougies provenant de sources différentes."""
    anomalies = comparer_sources(
        demande.bougies_source_a,
        demande.bougies_source_b,
        tolerance_pct,
    )

    if anomalies:
        journaliser_decision(
            "anomalie_reconciliation",
            anomalies[0].instrument_id,
            {
                "nb_anomalies": len(anomalies),
                "tolerance_pct": tolerance_pct,
            },
        )

    return anomalies


# ---------------------------------------------------------------------------
# LANCEMENT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
