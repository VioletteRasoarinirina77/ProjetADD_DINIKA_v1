\# DINIKA - Provenance des données Quant



Version du dataset : 1.0

Dataset : ES\_quant\_daily\_v1.0.csv



\## 1. Source principale



La source principale des données de marché est Databento.



Source :

Databento



Dataset :

GLBX.MDP3



Instrument :

ES - E-mini S\&P 500 Futures



Symbole continu utilisé pour l'OHLCV :

ES.v.0



\## 2. Rôle de CME



CME est utilisé comme source de référence pour les informations contractuelles du produit ES.



CME sert notamment à documenter :



\- l'identification du contrat ;

\- le multiplicateur ;

\- le tick minimum ;

\- la valeur du tick ;

\- le cycle des contrats ;

\- les échéances ;

\- les horaires de marché ;

\- les informations générales sur le produit.



CME n'est pas la source principale des OHLCV historiques du dataset Quant v1.0.



\## 3. Pipeline de préparation



Le flux général est :



Databento

&#x20;   ↓

Ingestion

&#x20;   ↓

Normalisation DINIKA

&#x20;   ↓

Validation

&#x20;   ↓

Historisation / préparation du contrat continu

&#x20;   ↓

Nettoyage et contrôle qualité

&#x20;   ↓

Calcul des variables dérivées

&#x20;   ↓

Dataset Quant v1.0



\## 4. OHLCV



Les données OHLCV proviennent de Databento.



Les champs principaux sont :



\- timestamp

\- open

\- high

\- low

\- close

\- volume



Les contrôles suivants sont appliqués :



\- présence des colonnes obligatoires ;

\- valeurs manquantes ;

\- cohérence OHLC ;

\- volume négatif ;

\- ordre chronologique ;

\- doublons ;

\- cohérence des identifiants.



\## 5. Contrat continu



Le dataset utilise l'identifiant instrument `ES`.



La colonne `contract\_instrument\_id` conserve l'identifiant du contrat réel correspondant à chaque observation.



Le contrat continu est construit à partir des contrats ES individuels.



La logique de roll utilise notamment l'Open Interest lorsque celui-ci est disponible.



\## 6. Ajustement



Une colonne `cumulative\_adjustment\_factor` est conservée afin de documenter l'ajustement appliqué à la série continue.



Cette information permet de distinguer la série continue préparée pour l'analyse de la donnée brute d'un contrat individuel.



\## 7. Open Interest



Open Interest provient des statistiques de marché disponibles dans Databento.



Il est associé au contrat correspondant.



Lorsque aucune valeur exploitable n'est disponible, la valeur est conservée comme NaN.



Aucune valeur manquante n'est remplacée artificiellement par zéro.



\## 8. Settlement



Settlement Price provient des statistiques disponibles dans Databento lorsqu'une valeur exploitable est disponible.



Les valeurs indisponibles restent NaN.



\## 9. Timestamp



Les timestamps du dataset Quant sont normalisés en UTC.



Convention :



YYYY-MM-DD 00:00:00+00:00



Le timestamp quotidien ne doit pas être interprété comme une heure d'ouverture du marché.



\## 10. Validation du dataset v1.0



Résultats du contrôle qualité :



\- lignes : 4453

\- colonnes : 36

\- doublons timestamp : 0

\- doublons timestamp + instrument : 0

\- lignes OHLC invalides : 0

\- volumes négatifs : 0

\- Open Interest négatif : 0

\- ordre chronologique : valide

\- gaps calendaires > 3 jours : 3



Les gaps calendaires sont documentés dans :



quality/GAPS.json



Ils ne sont pas automatiquement considérés comme des erreurs.



\## 11. Dataset gelé



Le fichier officiel est :



dataset/ES\_quant\_daily\_v1.0.csv



SHA-256 :



23af73a8a6160b45ead19c53503bf5ef56b1a010a63535297eecbc4b1dbb83ac



Le fichier v1.0 ne doit plus être modifié.



Toute modification doit produire une nouvelle version du dataset.



\## 12. Utilisation par Quant



Quant doit utiliser le dataset :



dataset/ES\_quant\_daily\_v1.0.csv



Les règles d'utilisation sont définies dans :



contract/DATA\_CONTRACT.md



Les contrôles qualité sont définis dans :



quality/QUALITY\_REPORT.json

quality/GAPS.json

quality/MISSING\_VALUES.md

