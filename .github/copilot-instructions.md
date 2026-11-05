# Projet Truetone
Truetone est un registre de création musicale en ligne pour artistes indépendants.
L'artiste dépose son morceau et ses fichiers de travail, déclare s'il a utilisé l'IA
et à quelle étape, et reçoit un certificat PDF avec la date et l'empreinte SHA-256.
Une page publique permet de vérifier un fichier.
## Règles
- Nous sommes débutantes : explique chaque modification en français simple.
- Python 3 + Streamlit uniquement. Un seul fichier principal : app.py.
- Bibliothèques autorisées : streamlit, fpdf2, qrcode, pandas. Liste-les dans requirements.txt.
- On ne stocke jamais les fichiers audio, seulement leur empreinte SHA-256.
- Les données sont dans un fichier SQLite : registre.db.
- Les dates sont en UTC, au format ISO 8601.
- Interface en français, sobre, couleurs : noir, blanc et violet.
- Avance par petites étapes et dis-moi comment tester après chaque étape.
