---
name: empreinte-fichier
description: Calcule l'empreinte SHA-256 d'un fichier déposé dans Truetone et l'enregistre dans le registre SQLite. À utiliser pour tout ce qui touche au dépôt, au hash ou à la vérification d'un fichier.
---
# Empreinte d'un fichier
1. Lire le fichier par blocs de 1 Mo avec hashlib.sha256.
2. Ne jamais écrire le fichier sur le disque.
3. Table SQLite depots : id, numero_certificat (format TT-AAAA-XXXXXX), artiste, titre, nom_fichier, empreinte, date_utc, ia_utilisee (oui/non), etapes_ia, commentaire.
4. Si l'empreinte existe déjà, ne pas créer de doublon : afficher le dépôt existant et sa date.
