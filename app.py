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
        certificat=numero_certificat,
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
    pdf.ln(4)
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


def rechercher_depot_verification(valeur, par_empreinte=False):
    colonne = "empreinte" if par_empreinte else "numero_certificat"
    connexion = sqlite3.connect(REGISTRE_DB, timeout=10)
    try:
        return connexion.execute(
            f"""
            SELECT numero_certificat, date_utc, artiste, titre, ia_utilisee,
                   etapes_ia
            FROM depots
            WHERE {colonne} = ?
            """,
            (valeur,),
        ).fetchone()
    finally:
        connexion.close()


def lire_statistiques_depots():
    connexion = sqlite3.connect(REGISTRE_DB, timeout=10)
    try:
        total, avec_ia = connexion.execute(
            """
            SELECT COUNT(*),
                   COALESCE(SUM(CASE WHEN ia_utilisee = 'oui' THEN 1 ELSE 0 END), 0)
            FROM depots
            """
        ).fetchone()
        part_ia = avec_ia / total * 100 if total else 0
        return total, part_ia
    finally:
        connexion.close()


def afficher_resultat_verification(depot):
    if depot is None:
        st.caption("Aucun enregistrement trouvé")
        return

    st.success("Fichier enregistré")
    st.write(f"**Numéro de certificat :** {depot[0]}")
    st.write(f"**Date UTC :** {depot[1]}")
    st.write(f"**Artiste :** {depot[2]}")
    st.write(f"**Titre :** {depot[3]}")
    if depot[4] == "oui":
        declaration_ia = (
            f"IA utilisée — {depot[5]}"
            if depot[5]
            else "IA utilisée, aucune étape précisée"
        )
    else:
        declaration_ia = "Aucune IA déclarée"
    st.write(f"**Déclaration IA :** {declaration_ia}")


st.set_page_config(page_title="Truetone", layout="wide")

numero_certificat_url = (
    st.query_params.get("certificat", "")
    or st.query_params.get("numero_certificat", "")
)
page_demandee = st.query_params.get("page")
if "navigation_page" not in st.session_state:
    if page_demandee in ("Accueil", "Déposer", "Vérifier"):
        st.session_state.navigation_page = page_demandee
    else:
        st.session_state.navigation_page = "Vérifier" if numero_certificat_url else "Accueil"


def changer_page(nouvelle_page):
    st.session_state.navigation_page = nouvelle_page

page = st.sidebar.radio(
    "Navigation",
    ["Accueil", "Déposer", "Vérifier"],
    key="navigation_page",
)

if page == "Accueil":
    st.markdown(
        """
        <style>
        .hero {
            padding: 3rem 0 2.2rem;
            border-bottom: 1px solid rgba(167, 139, 250, 0.25);
        }
        .hero h1 {
            margin: 0;
            font-size: clamp(3.5rem, 9vw, 6.5rem);
            line-height: 1;
            letter-spacing: -0.07em;
        }
        .hero .slogan {
            max-width: 760px;
            margin: 1.4rem 0 0;
            color: #c4b5fd;
            font-size: clamp(1.2rem, 2.5vw, 1.8rem);
            line-height: 1.4;
        }
        .intro {
            max-width: 780px;
            padding: 2rem 0 1rem;
            color: #d4d4d8;
            font-size: 1.05rem;
            line-height: 1.8;
        }
        .step-card {
            min-height: 150px;
            padding: 1.3rem;
            border: 1px solid rgba(167, 139, 250, 0.25);
            border-radius: 12px;
            background: #17171f;
        }
        .step-number {
            color: #a78bfa;
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.12em;
        }
        .step-icon {
            display: grid;
            width: 2.7rem;
            height: 2.7rem;
            margin-top: 1.1rem;
            place-items: center;
            border-radius: 10px;
            background: rgba(139, 92, 246, 0.16);
            color: #c4b5fd;
            font-size: 1.5rem;
        }
        .step-card h3 {
            margin: 0.65rem 0 0.35rem;
            color: #fafafa;
            font-size: 1.2rem;
        }
        .step-card p {
            margin: 0;
            color: #a1a1aa;
        }
        </style>
        <section class="hero">
            <h1>Truetone</h1>
            <p class="slogan">Chaque artiste peut prouver ce qu'il a créé,
            chaque auditeur sait ce qu'il écoute</p>
        </section>
        <section class="intro">
            <p>Plus de 50 % des nouvelles sorties sur Deezer sont générées par IA.</p>
            <p>Dans ce contexte, il devient plus difficile de distinguer les œuvres
            et de connaître leur origine.</p>
            <p>Les artistes indépendants ont du mal à prouver leurs créations.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    try:
        nombre_depots, part_ia = lire_statistiques_depots()
    except (OSError, sqlite3.Error) as erreur:
        st.error(f"Impossible de lire les statistiques du registre : {erreur}")
    else:
        colonnes_stats = st.columns(2)
        colonnes_stats[0].metric("Dépôts enregistrés", f"{nombre_depots:,}".replace(",", " "))
        colonnes_stats[1].metric("Dépôts déclarant de l'IA", f"{part_ia:.1f} %")

    st.subheader("En trois étapes")
    colonnes_etapes = st.columns(3)
    etapes_accueil = [
        ("01", "↓", "Déposez", "Ajoutez votre morceau et ses éléments de création."),
        ("02", "✳", "Déclarez l'IA", "Indiquez si et comment vous avez utilisé l'IA."),
        ("03", "✓", "Recevez votre certificat", "Obtenez une preuve horodatée de votre dépôt."),
    ]
    for colonne, (numero, icone, titre_etape, description) in zip(
        colonnes_etapes, etapes_accueil
    ):
        with colonne:
            st.markdown(
                f"""
                <div class="step-card">
                    <span class="step-number">{numero} / 03</span>
                    <div class="step-icon">{icone}</div>
                    <h3>{titre_etape}</h3>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.write("")
    colonnes_actions = st.columns(2)
    with colonnes_actions[0]:
        st.button(
            "Déposer",
            type="primary",
            use_container_width=True,
            on_click=changer_page,
            args=("Déposer",),
        )
    with colonnes_actions[1]:
        st.button(
            "Vérifier",
            use_container_width=True,
            on_click=changer_page,
            args=("Vérifier",),
        )

elif page == "Déposer":
    st.title(page)
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
                        on_click="ignore",
                        key=f"telecharger_{resultat['numero_certificat']}",
                    )
elif page == "Vérifier":
    st.title(page)
    st.subheader("Par numéro de certificat")
    numero_certificat = st.text_input(
        "Numéro du certificat",
        value=numero_certificat_url,
    ).strip()
    if numero_certificat:
        try:
            depot = rechercher_depot_verification(numero_certificat)
        except sqlite3.Error as erreur:
            st.error(f"Impossible de vérifier le certificat : {erreur}")
        else:
            afficher_resultat_verification(depot)

    st.divider()
    st.subheader("Par fichier")
    fichier_a_verifier = st.file_uploader(
        "Choisissez un fichier à vérifier",
        type=["mp3", "wav", "flac", "aiff", "zip", "pdf"],
        key="fichier_a_verifier",
    )
    if fichier_a_verifier is not None:
        try:
            empreinte = calculer_empreinte(fichier_a_verifier)
            depot = rechercher_depot_verification(empreinte, par_empreinte=True)
        except (OSError, sqlite3.Error) as erreur:
            st.error(f"Impossible de vérifier le fichier : {erreur}")
        else:
            afficher_resultat_verification(depot)
