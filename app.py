import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

REGISTRE_DB = Path(__file__).with_name("registre.db")


def calculer_empreinte(fichier):
    empreinte = hashlib.sha256()
    fichier.seek(0)
    while True:
        bloc = fichier.read(1024 * 1024)
        if not bloc:
            break
        empreinte.update(bloc)
    fichier.seek(0)
    return empreinte.hexdigest()


def enregistrer_depots(fichiers, artiste, titre, ia_utilisee, etapes_ia, commentaire):
    resultats = []
    empreintes_traitees = set()
    connexion = sqlite3.connect(REGISTRE_DB, timeout=10)
    try:
        with connexion:
            connexion.execute(
                """
                CREATE TABLE IF NOT EXISTS depots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_certificat TEXT NOT NULL UNIQUE,
                    artiste TEXT NOT NULL,
                    titre TEXT NOT NULL,
                    nom_fichier TEXT NOT NULL,
                    empreinte TEXT NOT NULL UNIQUE,
                    date_utc TEXT NOT NULL,
                    ia_utilisee TEXT NOT NULL CHECK (ia_utilisee IN ('oui', 'non')),
                    etapes_ia TEXT NOT NULL,
                    commentaire TEXT NOT NULL
                )
                """,
            )
            connexion.execute("BEGIN IMMEDIATE")

            for fichier in fichiers:
                empreinte = calculer_empreinte(fichier)
                if empreinte in empreintes_traitees:
                    continue
                empreintes_traitees.add(empreinte)

                depot_existant = connexion.execute(
                    """
                    SELECT numero_certificat, date_utc
                    FROM depots
                    WHERE empreinte = ?
                    """,
                    (empreinte,),
                ).fetchone()

                if depot_existant:
                    resultats.append(
                        {
                            "existant": True,
                            "numero_certificat": depot_existant[0],
                            "date_utc": depot_existant[1],
                        }
                    )
                    continue

                annee = datetime.now(timezone.utc).year
                while True:
                    numero_certificat = (
                        f"TT-{annee}-{secrets.randbelow(1_000_000):06d}"
                    )
                    certificat_utilise = connexion.execute(
                        "SELECT 1 FROM depots WHERE numero_certificat = ?",
                        (numero_certificat,),
                    ).fetchone()
                    if not certificat_utilise:
                        break

                date_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
                connexion.execute(
                    """
                    INSERT INTO depots (
                        numero_certificat, artiste, titre, nom_fichier, empreinte,
                        date_utc, ia_utilisee, etapes_ia, commentaire
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        numero_certificat,
                        artiste,
                        titre,
                        fichier.name,
                        empreinte,
                        date_utc,
                        "oui" if ia_utilisee else "non",
                        ", ".join(etapes_ia),
                        commentaire,
                    ),
                )
                resultats.append(
                    {
                        "fichier": fichier.name,
                        "empreinte": empreinte,
                        "existant": False,
                        "numero_certificat": numero_certificat,
                        "date_utc": date_utc,
                    }
                )
    finally:
        connexion.close()

    return resultats


st.set_page_config(page_title="Truetone")

page = st.sidebar.radio("Navigation", ["Déposer", "Vérifier"])

st.title(page)

if page == "Déposer":
    st.caption("Présentez votre morceau et les fichiers qui documentent sa création.")

    ia_utilisee = st.checkbox("J'ai utilisé l'IA", key="ia_utilisee")
    artiste = st.text_input("Nom d'artiste *", key="artiste")
    titre = st.text_input("Titre du morceau *", key="titre")
    fichiers = st.file_uploader(
        "Fichier(s) du morceau *",
        type=["mp3", "wav", "flac", "aiff", "zip", "pdf"],
        accept_multiple_files=True,
    )

    etapes_ia = []
    if ia_utilisee:
        st.markdown("**À quelles étapes avez-vous utilisé l'IA ?**")
        colonnes = st.columns(4)
        etapes = [
            "Composition",
            "Paroles",
            "Voix",
            "Instruments",
            "Mixage",
            "Mastering",
            "Pochette",
        ]
        for index, etape in enumerate(etapes):
            with colonnes[index % len(colonnes)]:
                if st.checkbox(etape, key=f"etape_ia_{index}"):
                    etapes_ia.append(etape)

    commentaire = st.text_area("Commentaire (facultatif)", key="commentaire")
    valider = st.button("Valider et afficher le résumé")

    if valider:
        erreurs = []
        if not artiste.strip():
            erreurs.append("Indiquez le nom d'artiste.")
        if not titre.strip():
            erreurs.append("Indiquez le titre du morceau.")
        if not fichiers:
            erreurs.append("Ajoutez au moins un fichier.")

        if erreurs:
            for erreur in erreurs:
                st.error(erreur)
        else:
            try:
                resultats = enregistrer_depots(
                    fichiers,
                    artiste.strip(),
                    titre.strip(),
                    ia_utilisee,
                    etapes_ia,
                    commentaire.strip(),
                )
            except (OSError, sqlite3.Error) as erreur:
                st.error(f"Impossible d'enregistrer le dépôt : {erreur}")
            else:
                st.divider()
                st.subheader("Résultat du dépôt")
                if any(not resultat["existant"] for resultat in resultats):
                    st.write(f"**Artiste :** {artiste.strip()}")
                    st.write(f"**Morceau :** {titre.strip()}")
                    st.write(
                        f"**Utilisation de l'IA :** {'Oui' if ia_utilisee else 'Non'}"
                    )
                if ia_utilisee and any(
                    not resultat["existant"] for resultat in resultats
                ):
                    st.write(
                        "**Étapes concernées :** "
                        + (", ".join(etapes_ia) if etapes_ia else "Aucune étape sélectionnée")
                    )
                if any(not resultat["existant"] for resultat in resultats):
                    st.write(
                        f"**Commentaire :** {commentaire.strip() or 'Aucun commentaire'}"
                    )
                for resultat in resultats:
                    if resultat["existant"]:
                        st.write(
                            f"**Numéro de certificat :** "
                            f"{resultat['numero_certificat']}"
                        )
                        st.write(f"**Date UTC :** {resultat['date_utc']}")
                    else:
                        st.success(f"Dépôt enregistré : {resultat['fichier']}.")
                        st.write(
                            f"**Numéro de certificat :** "
                            f"{resultat['numero_certificat']}"
                        )
                        st.write(f"**Date UTC :** {resultat['date_utc']}")
                        st.write("**Empreinte SHA-256 :**")
                        st.code(resultat["empreinte"])
