\# DINIKA - API / Accès aux données pour Quant



Version du dataset : 1.0

Dataset officiel : ES\_quant\_daily\_v1.0.csv



\## 1. Dataset officiel



Le dataset à utiliser par le moteur Quant est :



dataset/ES\_quant\_daily\_v1.0.csv



Il s'agit du dataset quotidien officiel ES de DINIKA DATA v1.0.



\## 2. Accès recommandé



Pour la version v1.0, Quant lit directement le fichier CSV gelé.



Chemin relatif depuis la racine du pack :



dataset/ES\_quant\_daily\_v1.0.csv



Aucune connexion directe à Databento n'est nécessaire pour utiliser le dataset gelé.



\## 3. Exemple Python



```python

import pandas as pd



path = "dataset/ES\_quant\_daily\_v1.0.csv"



df = pd.read\_csv(

&#x20;   path,

&#x20;   parse\_dates=\["timestamp"]

)



print(df.head())

print(df.shape)

