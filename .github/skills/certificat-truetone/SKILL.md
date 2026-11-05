---
name: certificat-truetone
description: Génère le certificat PDF Truetone d'un dépôt. À utiliser quand on parle de certificat, de PDF ou de preuve d'antériorité.
---
# Certificat Truetone
Utiliser fpdf2, A4 portrait. Contenu dans l'ordre :
1. Titre « Certificat de création Truetone » et numéro de certificat.
2. Artiste, titre du morceau, nom du fichier.
3. Date et heure du dépôt (UTC).
4. Empreinte SHA-256 en police monospace.
5. Déclaration IA : « Aucune IA déclarée » ou la liste des étapes.
6. Un QR code vers la page Vérifier avec le numéro du certificat.
7. Mention : « Ce certificat atteste qu'un fichier ayant cette empreinte a été déposé à cette date. La déclaration IA est faite sur l'honneur par l'artiste. »
Retourner le PDF en mémoire (bytes) pour st.download_button.
