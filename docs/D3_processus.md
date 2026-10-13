# D3 — Backtesting walk-forward : processus complet, de la donnée au résultat

> **À quoi sert ce document.** Comprendre, expliquer et démontrer D3 sans lire tout le code.
> Chaque étape indique : l'**entrée**, le **fichier et la fonction**, le **traitement**, la **sortie** (avec sa forme),
> un **exemple réel** tiré du PACK ES, et la **commande de test** qui le prouve.
> Tous les chiffres ont été relevés sur le code actuel et le PACK ES v1.0 (4453 bougies, capital 2 000 000 $).

**Critères du cahier des charges (CDC §5.2) pour D3 :** protocole hors-échantillon ; déterministe (graine fixée) ;
métriques honnêtes (taux de réussite, Sharpe, drawdown max) ; rapport reproductible.

---

## 1. En une page

D3 vérifie, **sur des données que la calibration n'a jamais vues**, si la stratégie de référence
(« acheter quand le Close passe au-dessus de sa moyenne mobile de 20 jours ») aurait gagné de l'argent, en tenant
compte des coûts. Le résultat sert à **valider le protocole**, pas à promettre un gain.

```text
D2 (indicateurs)  →  signal d'entrée  →  fenêtres [TRAIN][TEST]  →  calibration sur TRAIN
        →  simulation sur TEST  →  courbe d'equity  →  métriques  →  ValidationBacktest  →  rapport / API / D7
```

| Question | Réponse |
|---|---|
| Quel point d'entrée ? | `backtest/walk_forward.py` → `walk_forward_backtest(bougies, "ES", taille_train, taille_test)` |
| Quelle règle de stratégie ? | `strategy/rules.py` : croisement haussier du Close au-dessus de la SMA-20 |
| Qui simule les trades ? | `backtest/simulator.py` → `simuler_trades()` |
| Qui fixe stop, take-profit, taille ? | D4 (`risk/`), appelé à chaque entrée |
| Que calibre-t-on ? | Le multiplicateur ATR du stop, parmi 1,5 ; 2,0 ; 2,5 ; 3,0 |
| Qu'est-ce qui sort ? | `ValidationBacktest` : Sharpe, drawdown max, taux de réussite, nombre de trades |
| Qui l'utilise ? | API `GET /backtest`, rapport Markdown, panneau D7 |

---

## 2. Les fichiers

| Fichier | Rôle dans D3 |
|---|---|
| `integration/pack_repository.py`, `charger_donnees_pack.py` | données (voir D2, étape 1) |
| `indicators/technical.py` | indicateurs : SMA-20 (signal), ATR-14 (stop et taille) |
| `strategy/rules.py` | **la règle** : `generer_signaux_entree` ; **`ajouter_signaux`** (signal sur la série continue) |
| `backtest/walk_forward.py` | **orchestration** : découpage, calibration, boucle sur les fenêtres |
| `backtest/simulator.py` | **simulation** : entrées, sorties, PnL de chaque trade |
| `backtest/equity.py` | courbe d'equity en dollars, valorisée au Close |
| `backtest/metrics.py` | Sharpe, drawdown, taux de réussite |
| `risk/position_sizing.py`, `stops.py`, `exposure.py` | **D4** : taille, stop-loss, take-profit (appelés par la simulation) |
| `scripts/generer_rapport_backtest.py` | rapport reproductible `docs/rapport_backtest_ES_v1.0.md` |

**D3 et D4.** D3 *utilise* les règles de risque pour simuler la stratégie : à chaque entrée, il appelle
`calculer_risque()`. D4 *possède* ces calculs. D4 n'est donc pas une étape qui vient après D3.

---

## 3. Étape par étape

### Étape 1 — Données

| | |
|---|---|
| **Entrée** | PACK ES v1.0 |
| **Fonction** | `PackDataRepository(...).candles_validees("ES")` |
| **Sortie** | `list[Bougie]`, 4453 éléments (SHA-256 vérifié, qualité contrôlée) |

Détail : voir `docs/D2_processus.md`, étape 1.

### Étape 2 — Préparation : indicateurs puis signal

| | |
|---|---|
| **Entrée** | les bougies |
| **Fonctions** | `bougies_vers_dataframe` → `ajouter_indicateurs` (D2) → **`ajouter_signaux`** (D3) |
| **Sortie** | tableau 4453 × 12 : OHLCV + 6 indicateurs + `signal_entree` (vrai/faux) |

**Règle du signal** (`strategy/rules.py`) :

```text
signal en t  =  Close(t) > SMA20(t)   ET   Close(t−1) ≤ SMA20(t−1)
```

Le signal est lu **à la clôture de t** : il n'utilise aucune information future.

**Point essentiel : le signal est calculé UNE seule fois, sur toute la série continue.** Ensuite on découpe en
fenêtres, et chaque fenêtre hérite de la colonne `signal_entree`. Pourquoi ? Si on recalculait le signal sur chaque
fenêtre, la première bougie de la fenêtre ne connaîtrait pas la bougie précédente et déclarerait un croisement
**fictif** dès que le prix est déjà au-dessus de sa moyenne. Sur le PACK, cela touchait 47 fenêtres de test sur 70
avant la correction (décision D-016).

*Exemple réel :* sur les 4453 bougies, **247 vrais croisements** haussiers.

**Tests :** `pytest tests/backtest/test_signaux_continus.py --no-cov -q` → **11 passed** ;
`pytest tests/strategy --no-cov -q` → **4 passed**

### Étape 3 — Découpage train / test

| | |
|---|---|
| **Entrée** | le tableau complet, `taille_train`, `taille_test` |
| **Fonction** | `decouper_walk_forward(df, taille_train, taille_test)` |
| **Sortie** | liste de fenêtres `(train, test)` |

```text
fenêtre 1 :  [ TRAIN ........ ][ TEST ]
fenêtre 2 :        (avance de taille_test)  [ TRAIN ........ ][ TEST ]
fenêtre 3 :                                       (avance…)   [ TRAIN ........ ][ TEST ]
```

Les fenêtres de **test sont contiguës et sans chevauchement** ; les fenêtres de train se chevauchent. Le résultat final
ne provient **que** des fenêtres de test.

| Configuration | Fenêtres | Rôle |
|---|---:|---|
| 60 / 20 | 219 | démonstration (train court : peu de trades pour calibrer) |
| **250 / 60** | **70** | **configuration de référence** |
| 500 / 120 | 32 | référence à train plus long |

*Exemple réel, 250/60, première fenêtre :* train du 2012-02-29 au 2012-12-19, test du 2012-12-20 au 2013-03-04.
Les 250 premières bougies ne servent qu'à calibrer ; **4200 bougies** (70 × 60) sont évaluées en test.

**Tests :** `pytest tests/backtest/test_walk_forward.py --no-cov -q` → **11 passed**

### Étape 4 — Calibration sur TRAIN

| | |
|---|---|
| **Entrée** | une fenêtre TRAIN, le capital courant |
| **Fonction** | `calibrer_multiplicateur_atr(train, "ES", capital)` |
| **Traitement** | pour chaque k ∈ {1,5 ; 2,0 ; 2,5 ; 3,0} : simulation sur TRAIN, courbe d'equity, métriques ; **on retient le k au meilleur Sharpe** |
| **Sortie** | un multiplicateur k par fenêtre |
| **Cas limite** | si aucun k n'a de Sharpe calculable (aucun trade), la valeur de la configuration (2,5 pour ES) est conservée |

La fenêtre TEST n'est **jamais** utilisée pour calibrer. Le k choisi est ensuite appliqué tel quel au TEST.

*Exemple réel, 250/60 :* k calibré = 1,5 dans 20 fenêtres, 2,0 dans 20, 2,5 dans 13, 3,0 dans 17. La première
fenêtre retient k = 1,5. Le choix change d'une fenêtre à l'autre : la calibration réagit bien aux données de son train.

**Tests :** `pytest tests/backtest/test_calibration.py --no-cov -q` → **3 passed**

### Étape 5 — Simulation sur TEST

| | |
|---|---|
| **Entrée** | une fenêtre TEST (avec `signal_entree`), k calibré, capital courant |
| **Fonction** | `simuler_trades(test, "ES", capital, k)` dans `backtest/simulator.py` |
| **Sortie** | liste de trades (dictionnaires) |

**Règles de la simulation, dans l'ordre :**

1. **Entrée** : si `signal_entree` est vrai en t, que l'ATR existe et qu'aucune position n'est ouverte, on entre à
   l'**Open de la bougie t+1** (jamais au Close du signal : on ne peut pas agir avant de connaître la clôture).
2. **D4 à l'entrée** : `calculer_risque()` donne, **une seule fois**, le stop-loss (`entrée − k × ATR`), le take-profit
   (`entrée + 2 × k × ATR`) et la taille (nombre **entier** de contrats, selon 1 % du capital courant).
3. **Position longue uniquement, une seule à la fois.**
4. **La bougie d'entrée n'est pas testée pour une sortie** : on ne sait pas, avec des données OHLC, si le plus haut
   ou le plus bas est arrivé en premier. La vérification commence à la bougie suivante.
5. **Sortie** : stop touché (`low ≤ stop`) ou take-profit touché (`high ≥ take-profit`). **Si les deux sont touchés
   sur la même bougie, le stop est retenu** (hypothèse prudente).
6. **Gap** : si la bougie ouvre déjà **sous le stop**, la sortie se fait à l'**Open** (le prix du stop n'a jamais été
   coté). Le take-profit est toujours exécuté à son propre prix, même si la bougie ouvre au-dessus : on ne
   comptabilise aucun gain de gap (décision D-017).
7. **Coût** : `pnl_points = prix_sortie − prix_entrée − spread` (0,5 point pour ES, appliqué une fois, à la sortie) ;
   `pnl_dollars = pnl_points × 50 × taille`.
8. **Position encore ouverte à la fin de la fenêtre** : non comptée (décision D-007, à valider par l'encadreur).

*Exemple réel — le premier trade du backtest 250/60 :*

```text
entrée  2013-01-02 au prix 1280.83      sortie  2013-01-28 au prix 1331.10 (take-profit)
taille 15 contrats                      pnl_points = 1331.10 − 1280.83 − 0.5 = +49.77
pnl_dollars = 49.77 × 50 × 15 = +37 330 $
```

Sur la totalité : **82 trades** (28 gagnants), taille de 1 à 25 contrats (moyenne 7,8), 18 fenêtres de test sans
aucun trade, 3 trades au maximum par fenêtre.

**Tests :** `pytest tests/backtest/test_signaux_continus.py --no-cov -q` → 11 passed (inclut les 4 cas de gap/stop/take-profit) ;
`pytest tests/backtest/test_simulateur_perf.py --no-cov -q` → **4 passed**

### Étape 6 — Courbe d'equity

| | |
|---|---|
| **Entrée** | la fenêtre TEST, ses trades, le capital de départ de la fenêtre |
| **Fonction** | `courbe_equity(...)` dans `backtest/equity.py` |
| **Sortie** | tableau de valeurs en **dollars**, une par bougie, précédé du capital initial |

```text
equity(t) = capital de départ + PnL des trades clôturés + PnL latent de la position ouverte (valorisée au Close de t)
```

Le capital réalisé à la fin d'une fenêtre **se reporte** à la suivante : la courbe est continue.

*Exemple réel, 250/60 :* courbe de 4201 valeurs (1 + 70 × 60), de 2 000 000 $ à **2 005 113 $** (+0,26 %).

**Tests :** `pytest tests/backtest/test_equity.py --no-cov -q` → **3 passed**

### Étape 7 — Métriques

| | |
|---|---|
| **Entrée** | tous les trades de test + la courbe d'equity complète |
| **Fonction** | `calculer_metriques()` dans `backtest/metrics.py` |
| **Sortie** | `ValidationBacktest` |

| Métrique | Définition |
|---|---|
| **Taux de réussite** | part des trades dont le PnL **en points** est positif (indépendant du capital et de la taille) |
| **Sharpe** | moyenne ÷ écart-type (ddof = 1) des rendements **journaliers** de l'equity en dollars, × √252 ; sans taux sans risque ; les jours sans position comptent pour un rendement nul |
| **Drawdown max** | plus forte baisse de l'equity depuis son sommet, en proportion du sommet (entre 0 et 1) |
| **Nombre de trades** | trades clôturés dans les fenêtres de test |

Si la taille recommandée est 0 (capital trop faible pour un contrat entier), l'equity reste plate : Sharpe et
drawdown valent 0, et le panneau D7 l'explique.

**Tests :** `pytest tests/backtest/test_metrics.py --no-cov -q` → **15 passed**

### Étape 8 — Résultats

| Train / Test | Fenêtres | Trades | Taux de réussite | Sharpe (√252) | Drawdown max |
|---:|---:|---:|---:|---:|---:|
| 60 / 20 | 219 | 67 | 13,4 % | −1,188 | 33,7 % |
| **250 / 60** | **70** | **82** | **34,1 %** | **0,019** | **17,8 %** |
| 500 / 120 | 32 | 86 | 36,0 % | 0,098 | 12,9 % |

**Lecture honnête.** Cette stratégie de référence n'est pas rentable, et le projet ne promet aucun gain. Sur 14,5 ans,
l'erreur-type du Sharpe annuel est d'environ 0,26 : **tous ces Sharpe sont indiscernables de zéro**. Ces résultats
valident l'**outillage** et le **protocole hors-échantillon**, pas une stratégie.

**Test de référence (valeurs exactes sur le PACK réel) :** `pytest tests/backtest/test_reference_pack_es.py --no-cov -q` → **1 passed**

**Où le résultat est utilisé :**

```text
ValidationBacktest ─┬─► API  GET /backtest/{instrument}
                    ├─► docs/rapport_backtest_ES_v1.0.md  (python -m scripts.generer_rapport_backtest)
                    └─► D7   panneau de risque (Sharpe, drawdown, taux de réussite, nombre de trades)
```

---

## 4. Ce qui a été corrigé, et pourquoi les chiffres ont changé

| Correction | Constat avant | Effet |
|---|---|---|
| **D-016** Signal sur la série continue | 47 fenêtres de test sur 70 commençaient par un faux croisement | 250/60 : 106 → 83 trades, Sharpe 0,186 → 0,002 |
| **D-017** Sortie au gap | un stop touché sortait toujours au prix du stop, même si la bougie ouvrait en dessous | 250/60 : 83 → 82 trades, Sharpe 0,002 → 0,019 |
| **D-019** Performance | `df.iloc[i]` coûtait 94 % du temps d'un backtest | synthèse D7 de 0,94 s à 0,11 s, **résultats strictement identiques** (2 570 comparaisons, 0 différence) |

Les anciens chiffres (Sharpe 0,186) étaient en partie des artefacts. Les nouveaux sont plus honnêtes.

---

## 5. Déterminisme et reproductibilité

- **Aucun tirage aléatoire** : la « graine fixée » du CDC est donc sans objet ; deux exécutions donnent exactement le
  même résultat.
- **Données gelées** : le SHA-256 du CSV est vérifié avant tout calcul ; une modification du fichier arrête le pipeline.
- **Rapport reproductible** : `python -m scripts.generer_rapport_backtest` écrit le rapport avec la version du dataset
  et son SHA-256 ; hors date de génération, il est identique d'une exécution à l'autre.

---

## 6. Commandes de test D3

> **Pourquoi `--no-cov` ?** Le projet impose une couverture globale de 75 %. En lançant seulement une partie des
> tests, la couverture totale est plus basse et la commande échouerait sur ce seuil, même si tous les tests passent.
> `--no-cov` désactive la mesure pour un lancement partiel. Remplacez `-q` par `-v` pour voir le nom de chaque test.

| # | Ce qu'on vérifie | Commande | Résultat attendu |
|---|---|---|---|
| 1 | Règle de signal : seulement au croisement, aucune dépendance au futur | `pytest tests/strategy --no-cov -q` | 4 passed |
| 2 | Signal sur série continue, gap, stop, take-profit, D8 | `pytest tests/backtest/test_signaux_continus.py --no-cov -q` | 11 passed |
| 3 | Découpage, simulation, déterminisme, paramètres invalides | `pytest tests/backtest/test_walk_forward.py --no-cov -q` | 11 passed |
| 4 | Calibration sur train uniquement | `pytest tests/backtest/test_calibration.py --no-cov -q` | 3 passed |
| 5 | Courbe d'equity | `pytest tests/backtest/test_equity.py --no-cov -q` | 3 passed |
| 6 | Métriques : Sharpe, drawdown, taux de réussite (valeurs calculées à la main) | `pytest tests/backtest/test_metrics.py --no-cov -q` | 15 passed |
| 7 | Séparation validation / hors-échantillon (D8) | `pytest tests/backtest/test_hors_echantillon.py --no-cov -q` | 10 passed |
| 8 | Organisation des modules (réexports) | `pytest tests/backtest/test_reexports.py --no-cov -q` | 4 passed |
| 9 | Version rapide identique à la version de référence | `pytest tests/backtest/test_simulateur_perf.py --no-cov -q` | 4 passed |
| 10 | **Valeurs de référence sur le PACK réel** (82 trades, Sharpe 0,019…) | `pytest tests/backtest/test_reference_pack_es.py --no-cov -q` | 1 passed |
| 11 | Rapport reproductible | `pytest tests/scripts/test_generer_rapport_backtest.py --no-cov -q` | 7 passed |
| 12 | **Tout D3 d'un coup** | `pytest tests/backtest --no-cov -q` | **62 passed** |

**Commandes ciblées utiles en démonstration :**

| But | Commande |
|---|---|
| Montrer le défaut corrigé (faux croisement sur une tranche) | `pytest tests/backtest/test_signaux_continus.py::test_une_tranche_seule_declare_un_faux_croisement_mais_pas_la_serie_continue --no-cov -v` |
| Prouver l'absence de fuite d'information | `pytest tests/strategy/test_rules.py::test_le_signal_a_l_instant_t_ne_depend_pas_du_futur --no-cov -v` |
| Prouver le déterminisme | `pytest tests/backtest/test_walk_forward.py::test_walk_forward_backtest_est_deterministe --no-cov -v` |
| Prouver que D8 ne calibre jamais sur le hors-échantillon | `pytest tests/backtest/test_hors_echantillon.py::test_d8_ne_calibre_jamais_sur_la_zone_hors_echantillon --no-cov -v` |
| Critère CDC D7 « synthèse < 3 s » | `pytest tests/dashboard/test_synthese.py::test_synthese_sur_le_pack_reel_es_sous_le_seuil_cdc_de_3_secondes --no-cov -q` |
| Régénérer le rapport de backtest | `python -m scripts.generer_rapport_backtest` |
| Voir le nom de tous les tests D3 | `pytest tests/backtest --no-cov -v` |
| Style du code D3 | `ruff check backtest strategy tests/backtest scripts` (« All checks passed! ») |
| Suite complète avec couverture | `pytest` (346 passed, couverture 99,38 %) |
| Couverture de D2/D3 seuls | `pytest tests/indicators tests/backtest tests/strategy --cov-fail-under=0` |

---

## 7. Preuve des exigences du CDC

| Exigence | Preuve | Commande |
|---|---|---|
| Protocole hors-échantillon | calibration sur train, résultat sur test uniquement ; D8 sépare validation et hors-échantillon | `pytest tests/backtest/test_calibration.py tests/backtest/test_hors_echantillon.py --no-cov -q` |
| Déterministe | `test_walk_forward_backtest_est_deterministe` | `pytest tests/backtest/test_walk_forward.py --no-cov -q` |
| Métriques honnêtes | valeurs vérifiées à la main ; signal sans faux croisement ; sortie au gap | `pytest tests/backtest/test_metrics.py tests/backtest/test_signaux_continus.py --no-cov -q` |
| Rapport reproductible | `test_le_rapport_est_reproductible_hors_date_de_generation` | `pytest tests/scripts/test_generer_rapport_backtest.py --no-cov -q` |
| Résultats vérifiés sur la donnée réelle | `test_walk_forward_250_60_sur_le_pack_es_reproduit_les_valeurs_de_reference` | `pytest tests/backtest/test_reference_pack_es.py --no-cov -q` |

---

## 8. Questions probables du jury

**Votre stratégie n'est pas rentable : à quoi sert ce travail ?**
À valider un **protocole**, pas une stratégie. Le Sharpe de 0,019 est indiscernable de zéro (erreur-type d'environ
0,26) et nous l'affirmons. Un protocole honnête doit être capable de dire « pas d'avantage statistique ».

**Comment garantissez-vous l'absence de fuite d'information du futur ?**
Le signal en t n'utilise que des données jusqu'à t (testé). L'entrée se fait à l'Open de t+1. La calibration n'utilise
que le train. Les fenêtres de test sont disjointes.

**Qu'avez-vous corrigé, et pourquoi les résultats ont-ils changé ?**
Un défaut aux bords des fenêtres créait des croisements fictifs : 47 fenêtres de test sur 70 en 250/60. Le corriger
a fait passer le Sharpe de 0,186 à 0,002 ; la sortie au gap l'a ramené à 0,019. Les anciens chiffres étaient en
partie des artefacts.

**Pourquoi un Sharpe annualisé par √252 alors que le PACK contient aussi les dimanches ?**
C'est une convention figée (D-009). Avec environ 307 bougies par an, √252 sous-estime légèrement le Sharpe (facteur
d'environ 1,10) ; ce choix prudent est assumé.

**Que devient une position ouverte à la fin d'une fenêtre ?**
Elle n'est pas comptée (D-007), ni dans les trades ni dans la courbe. C'est un point ouvert soumis à l'encadreur.
L'alternative serait de la clôturer au dernier Close.

**Pourquoi la configuration 60/20 donne-t-elle de mauvais résultats ?**
Un train de 60 bougies contient très peu de trades : la calibration travaille sur du bruit. La configuration de
référence est 250/60.

---

## 9. Limites et points ouverts

- **Position ouverte en fin de fenêtre** ignorée (D-007) : à valider.
- **Coûts simplifiés** : spread fixe de 0,5 point, sans commission ni glissement autre que le gap sous le stop.
- **Prix ajustés par ratio** (D-018) : série continue dont les anciens prix sont multipliés par un facteur de 0,87 à
  1,01. Les PnL en dollars des années anciennes sont exprimés en points ajustés (sous-estimés jusqu'à environ 13 %
  en 2012). Le niveau des prix passés dépend aussi de rolls ultérieurs : effet attendu faible sur un croisement
  Close/SMA, à mentionner comme limite. À confirmer avec la Piste Data.
- **Stratégie unique, longue seulement** : pas de modèle prédictif ni de score de confiance dans le périmètre actuel
  (question posée à l'encadreur).
- **D8 sur un seul instrument** : le CDC en demande deux ; le PACK ES seul ne le permet pas.
- **`paper_trading/portfolio.py`** conserve l'ancienne règle de sortie (au prix du stop) : à aligner à l'étape D8.