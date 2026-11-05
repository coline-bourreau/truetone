# Truetone
Registre de création musicale.

La page « Déposer » calcule l'empreinte SHA-256 des fichiers téléversés en mémoire
et enregistre chaque dépôt dans `registre.db`. Une empreinte déjà enregistrée
n'est pas ajoutée une seconde fois : l'application affiche alors le certificat
et la date du dépôt existant.

Pour lancer l'application :

```powershell
streamlit run app.py
```
