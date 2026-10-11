\# DINIKA - Conventions prix et volume



Version : 1.0

Instrument : ES - E-mini S\&P 500 Futures



\## 1. Prix



Les champs de prix sont exprimés en points d'indice S\&P 500.



Champs concernés :



\- open

\- high

\- low

\- close

\- settlement\_price



Les prix sont des valeurs numériques décimales.



\## 2. Cotation



Le contrat ES est coté en dollars américains par point d'indice.



Multiplicateur contractuel :



50 USD par point.



\## 3. Tick minimum



Variation minimale :



0.25 point.



Valeur d'un tick :



12.50 USD par contrat.



\## 4. Volume



Le volume représente le nombre d'unités/contracts échangés selon la convention de la donnée source.



Le volume est une valeur numérique non négative.



Une valeur négative est considérée comme invalide.



\## 5. Open Interest



Open Interest représente le nombre de contrats ouverts selon la donnée de marché disponible.



Il ne doit pas être confondu avec le volume.



Open Interest peut être absent lorsque la source ne fournit pas de valeur exploitable.



Une valeur absente reste NaN.



Elle ne doit pas être remplacée par zéro sans justification.



\## 6. Settlement Price



Settlement Price correspond à la valeur de règlement fournie par la source lorsqu'elle est disponible.



Elle peut être absente.



\## 7. Unités



Prix :

points d'indice S\&P 500



Volume :

contracts



Open Interest :

contracts



Devise contractuelle :

USD



Multiplicateur :

50 USD / point



Tick :

0.25 point



Valeur du tick :

12.50 USD



\## 8. Contrôle Quant



Quant doit conserver les unités d'origine et ne doit pas appliquer de conversion implicite.



Toute conversion doit être explicitement documentée dans le code ou le résultat produit.

