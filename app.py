import hashlib
import os
import secrets
import sqlite3
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import qrcode
import streamlit as st
from fpdf import FPDF

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
                    SELECT numero_certificat, date_utc, artiste, titre, nom_fichier,
                           empreinte, ia_utilisee, etapes_ia
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
                            "artiste": depot_existant[2],
                            "titre": depot_existant[3],
                            "fichier": depot_existant[4],
                            "empreinte": depot_existant[5],
                            "ia_utilisee": depot_existant[6] == "oui",
                            "etapes_ia": depot_existant[7],
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
                        "artiste": artiste,
                        "titre": titre,
                        "ia_utilisee": ia_utilisee,
                        "etapes_ia": ", ".join(etapes_ia),
                    }
                )
    finally:
        connexion.close()

    return resultats


def creer_url_verification(numero_certificat):
    base_url = os.environ.get("TRUETONE_PUBLIC_URL", st.context.url)
    url = urlsplit(base_url)
    parametres = dict(parse_qsl(url.query, keep_blank_values=True))
    parametres.update(
        page="Vérifier",
        numero_certificat=numero_certificat,
    )
    return urlunsplit(
        (url.scheme, url.netloc, url.path, urlencode(parametres), "")
    )


def generer_certificat(resultat):
    def texte_pdf(texte):
        substitutions = str.maketrans(
            {
                "\u2013": "-",
                "\u2014": "-",
                "\u2018": "'",
                "\u2019": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u2026": "...",
            }
        )
        return str(texte).translate(substitutions).encode(
            "latin-1", errors="replace"
        ).decode("latin-1")

    declaration_ia = (
        resultat["etapes_ia"] or "IA déclarée, aucune étape sélectionnée"
        if resultat["ia_utilisee"]
        else "Aucune IA déclarée"
    )

    qr_image = qrcode.make(
        creer_url_verification(resultat["numero_certificat"])
    )
    qr_buffer = BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 18)
    pdf.multi_cell(
        0,
        10,
        texte_pdf("Certificat de création Truetone"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(
        0,
        9,
        texte_pdf(f"Numéro de certificat : {resultat['numero_certificat']}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(4)
    pdf.set_font("helvetica", size=11)
    pdf.multi_cell(
        0,
        7,
        texte_pdf(f"Artiste : {resultat['artiste']}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.multi_cell(
        0,
        7,
        texte_pdf(f"Titre du morceau : {resultat['titre']}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.multi_cell(
        0,
        7,
        texte_pdf(f"Nom du fichier : {resultat['fichier']}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.multi_cell(
        0,
        7,
        texte_pdf(f"Date et heure du dépôt (UTC) : {resultat['date_utc']}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(3)
    pdf.cell(
        0,
        7,
        texte_pdf("Empreinte SHA-256 :"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("courier", size=9)
    empreinte = resultat["empreinte"]
    empreinte_formatee = "\n".join(
        empreinte[index : index + 32] for index in range(0, len(empreinte), 32)
    )
    pdf.multi_cell(
        0,
        6,
        texte_pdf(empreinte_formatee),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("helvetica", size=11)
    pdf.ln(3)
    pdf.multi_cell(
        0,
        7,
        texte_pdf(f"Déclaration IA : {declaration_ia}"),
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(3)
    pdf.multi_cell(
        0,
        7,
        texte_pdf("Vérifier ce certificat avec le QR code :"),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    qr_size = 35
    pdf.image(qr_buffer, x=(210 - qr_size) / 2, w=qr_size)
    pdf.ln(qr_size + 4)
    pdf.set_font("helvetica", size=9)
    pdf.multi_cell(
        0,
        6,
        texte_pdf(
            "Ce certificat atteste qu'un fichier ayant cette empreinte a été "
            "déposé à cette date. La déclaration IA est faite sur l'honneur "
            "par l'artiste."
        ),
        new_x="LMARGIN",
        new_y="NEXT",
    )
    return bytes(pdf.output())


st.set_page_config(page_title="Truetone")

numero_certificat_url = st.query_params.get("numero_certificat", "")
page_demandee = st.query_params.get("page")
if "navigation_page" not in st.session_state:
    if page_demandee in ("Déposer", "Vérifier"):
        st.session_state.navigation_page = page_demandee
    else:
        st.session_state.navigation_page = (
            "Vérifier" if numero_certificat_url else "Déposer"
        )

page = st.sidebar.radio(
    "Navigation",
    ["Déposer", "Vérifier"],
    key="navigation_page",
)

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
                        st.info("Ce fichier a déjà été déposé.")
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
                    st.download_button(
                        "Télécharger le certificat PDF",
                        data=generer_certificat(resultat),
                        file_name=(
                            f"certificat-{resultat['numero_certificat']}.pdf"
                        ),
                        mime="application/pdf",
                        key=f"telecharger_{resultat['numero_certificat']}",
                    )
elif page == "Vérifier":
    numero_certificat = st.text_input(
        "Numéro du certificat",
        value=numero_certificat_url,
    ).strip()
    if numero_certificat:
        try:
            with sqlite3.connect(REGISTRE_DB, timeout=10) as connexion:
                depot = connexion.execute(
                    """
                    SELECT artiste, titre, nom_fichier, empreinte, date_utc,
                           ia_utilisee, etapes_ia
                    FROM depots
                    WHERE numero_certificat = ?
                    """,
                    (numero_certificat,),
                ).fetchone()
        except sqlite3.Error as erreur:
            st.error(f"Impossible de vérifier le certificat : {erreur}")
        else:
            if depot is None:
                st.error("Aucun dépôt ne correspond à ce numéro de certificat.")
            else:
                st.success("Certificat vérifié : dépôt trouvé dans le registre.")
                st.write(f"**Artiste :** {depot[0]}")
                st.write(f"**Morceau :** {depot[1]}")
                st.write(f"**Fichier :** {depot[2]}")
                st.write(f"**Date UTC :** {depot[4]}")
                st.write(
                    f"**Utilisation de l'IA :** "
                    f"{'Oui' if depot[5] == 'oui' else 'Non'}"
                )
                if depot[5] == "oui":
                    st.write(f"**Étapes déclarées :** {depot[6] or 'Aucune'}")
                st.write("**Empreinte SHA-256 :**")
                st.code(depot[3])
