\# DINIKA - Data Contract Quant

Version : 1.0

Dataset : ES\_quant\_daily\_v1.0.csv



\## 1. Objet



Ce contrat définit le format officiel des données quotidiennes ES transmises au moteur Quant de DINIKA.



Le dataset est une série quotidienne historique de l'E-mini S\&P 500 Futures (ES), préparée pour l'analyse quantitative, les indicateurs et les traitements de recherche.



\## 2. Dataset officiel



Nom :

ES\_quant\_daily\_v1.0.csv



Version :

1.0



Fréquence :

Daily



Instrument :

ES - E-mini S\&P 500 Futures



Source principale :

Databento



Timezone :

UTC



Période disponible :

2012-02-29 à 2026-09-13



\## 3. Colonnes obligatoires



Les colonnes suivantes sont obligatoires :



\- timestamp

\- source

\- instrument\_id

\- contract\_instrument\_id

\- open

\- high

\- low

\- close

\- volume



Aucune valeur manquante n'est autorisée dans ces colonnes.



\## 4. Types attendus



timestamp :

Datetime avec timezone UTC.



source :

String.



instrument\_id :

String.



contract\_instrument\_id :

Identifiant numérique du contrat utilisé.



open :

Float.



high :

Float.



low :

Float.



close :

Float.



volume :

Entier ou valeur numérique non négative.



open\_interest :

Valeur numérique non négative lorsque disponible. Peut être NaN.



settlement\_price :

Float lorsque disponible. Peut être NaN.



\## 5. Règles OHLC



Pour chaque observation valide :



high >= open

high >= close

high >= low



low <= open

low <= close

low <= high



open > 0

high > 0

low > 0

close > 0



\## 6. Volume



Le volume doit être >= 0.



Une valeur négative constitue une anomalie.



\## 7. Open Interest



Open Interest est une donnée complémentaire.



Elle peut être absente lorsque la source ne fournit pas de valeur exploitable.



Une valeur manquante doit rester NaN.



Elle ne doit pas être remplacée silencieusement par 0.



\## 8. Settlement



Settlement Price est une donnée complémentaire.



Elle peut être absente lorsque la source ne fournit pas de valeur exploitable.



Une valeur manquante doit rester NaN.



\## 9. Timestamps



Les timestamps sont stockés en UTC.



Convention du dataset :



YYYY-MM-DD 00:00:00+00:00



Le timestamp ne doit pas être interprété comme l'heure d'ouverture du marché.



\## 10. Doublons



Deux observations ne doivent pas avoir le même :



timestamp + instrument\_id



Le dataset officiel v1.0 ne contient aucun doublon de ce type.



\## 11. Ordre temporel



Les observations sont triées chronologiquement.



Le timestamp doit être croissant.



\## 12. Valeurs manquantes



Les champs OHLCV obligatoires ne doivent pas contenir de valeur manquante.



Les champs complémentaires et indicateurs dérivés peuvent contenir NaN lorsque leur valeur n'est pas disponible ou lorsque leur calcul nécessite une fenêtre historique.



Aucune imputation silencieuse n'est appliquée.



\## 13. Gaps



Les intervalles calendaires supérieurs à 3 jours sont signalés dans :



quality/GAPS.json



Ces gaps ne sont pas automatiquement considérés comme des erreurs de données.



Ils doivent être interprétés avec la convention de session et de timestamp du dataset.



\## 14. Indicateurs dérivés



Le dataset contient également des variables quantitatives dérivées telles que :



\- returns

\- log return

\- SMA

\- EMA

\- ATR

\- volatilité

\- RSI

\- volume ratio

\- OI change

\- daily range

\- price position



Ces colonnes ne remplacent pas les données OHLCV source.



\## 15. Versioning



Le dataset v1.0 est gelé.



Toute modification du contenu doit produire une nouvelle version.



Exemple :



v1.1

v2.0



Il est interdit de modifier silencieusement ES\_quant\_daily\_v1.0.csv.



\## 16. Reproductibilité



SHA-256 du dataset officiel v1.0 :



23af73a8a6160b45ead19c53503bf5ef56b1a010a63535297eecbc4b1dbb83ac

