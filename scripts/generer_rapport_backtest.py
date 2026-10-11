"""Rapport de backtest walk-forward D3 sur le pack réel gelé (reproductible).

Usage (depuis la racine du dépôt) :
    python -m scripts.generer_rapport_backtest            # écrit docs/rapport_backtest_ES_v1.0.md

Traçabilité : le rapport mentionne la version du dataset, son SHA-256 (vérifié avant tout calcul par
`PackDataRepository`) et la période couverte. Le calcul est déterministe (aucun tirage aléatoire) :
deux exécutions produisent des chiffres strictement identiques (seule la date de génération change).

Ce rapport valide l'OUTILLAGE (protocole hors-échantillon, métriques, reproductibilité). Il ne présente
aucun résultat comme une promesse de gain : la stratégie de référence (croisement Close / SMA-20) est
volontairement simple.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from backtest.walk_forward import walk_forward_backtest
from config.instruments import resoudre_capital_virtuel
from integration.pack_repository import PackDataRepository

RACINE = Path(__file__).parent.parent
PACK_PAR_DEFAUT = RACINE / "fixtures" / "integration" / "pack_es_v1"
SORTIE_PAR_DEFAUT = RACINE / "docs" / "rapport_backtest_ES_v1.0.md"

# (taille_train, taille_test) en nombre de bougies quotidiennes.
CONFIGURATIONS_PAR_DEFAUT = [(60, 20), (250, 60), (500, 120)]


def generer_rapport(
    pack_dir: str | Path = PACK_PAR_DEFAUT,
    instrument_id: str = "ES",
    configurations: list[tuple[int, int]] | None = None,
    dernieres_bougies: int | None = None,
    capital_virtuel: float | None = None,
) -> str:
    """Construit le rapport Markdown. `dernieres_bougies` restreint la série (tests rapides).

    `capital_virtuel` : voir D-012 (`config.instruments.resoudre_capital_virtuel`). Par défaut (None),
    utilise le capital par défaut de l'instrument (2 000 000 $ pour ES) — nécessaire pour que la taille
    en contrats entiers (D4) et donc l'equity (D-009) soient représentatives, pas juste le PnL en points.
    """
    configurations = configurations or CONFIGURATIONS_PAR_DEFAUT
    depot = PackDataRepository(pack_dir)
    bougies = depot.candles_validees(instrument_id)  # vérifie le SHA-256 AVANT tout calcul
    provenance = depot.provenance()
    if dernieres_bougies is not None:
        bougies = bougies[-dernieres_bougies:]
    capital_affiche = resoudre_capital_virtuel(instrument_id, capital_virtuel)

    lignes = [
        f"# Rapport de backtest walk-forward — {instrument_id} (D3)",
        "",
        f"- Généré le : {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        f"- Dataset : version **{provenance['dataset_version']}**, "
        f"intégrité vérifiée : {provenance.get('integrite_verifiee')}",
        f"- SHA-256 : `{provenance['sha256']}`",
        f"- Bougies : {len(bougies)} ({bougies[0].timestamp:%Y-%m-%d} → {bougies[-1].timestamp:%Y-%m-%d}), "
        "quotidiennes, dimanches conservés",
        f"- Capital virtuel (D-012) : **{capital_affiche:,.0f} $**, contrat ES standard, 1 % de risque "
        "par trade, taille dimensionnée automatiquement en nombre entier de contrats (D4)",
        "- Stratégie : achat au croisement haussier Close / SMA-20, entrée à l'Open de t+1, stop et "
        "take-profit par ATR, position longue unique, coût = `spread_points` de la config",
        "- Protocole : fenêtres glissantes [train][test] ; multiplicateur ATR calibré sur train "
        "uniquement ; résultat issu des seules fenêtres test",
        "",
        "| Train | Test | Trades | Taux de réussite | Sharpe (annualisé √252) | Drawdown max (equity) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for taille_train, taille_test in configurations:
        r = walk_forward_backtest(bougies, instrument_id, taille_train, taille_test, capital_affiche)
        if r.nb_trades:
            lignes.append(
                f"| {taille_train} | {taille_test} | {r.nb_trades} | {r.taux_reussite:.1%} | "
                f"{r.sharpe:.3f} | {r.drawdown_max:.1%} |"
            )
        else:
            lignes.append(f"| {taille_train} | {taille_test} | 0 | n/a | n/a | n/a |")

    lignes += [
        "",
        "## Lecture honnête",
        "",
        "- Sharpe : rendements **journaliers** de la courbe d'equity, annualisé par **√252** "
        "(D-009, tranché par l'encadreur).",
        "- Drawdown max : chute maximale de la courbe d'**equity en dollars** (capital réel, taille en "
        "contrats entiers, coûts de transaction), en proportion du sommet précédent (D-009).",
        "- Position ouverte en fin de fenêtre : non comptée (D-007, à valider).",
        "- Taux de réussite : calculé sur le PnL en points (indépendant du capital et de la taille).",
        "- Ces chiffres valident le protocole et l'outillage. La stratégie de référence est volontairement "
        "simple ; aucun de ces résultats n'est une promesse de gain (outil d'aide à la décision).",
        "",
    ]
    return "\n".join(lignes)


def main() -> None:
    """Génère le rapport et l'écrit sur disque (point d'entrée `python -m scripts...`)."""
    contenu = generer_rapport()
    SORTIE_PAR_DEFAUT.write_text(contenu, encoding="utf-8")
    print(f"Rapport écrit : {SORTIE_PAR_DEFAUT.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
