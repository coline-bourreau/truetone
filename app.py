import streamlit as st

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
            st.divider()
            st.subheader("Résumé du dépôt")
            st.write(f"**Artiste :** {artiste.strip()}")
            st.write(f"**Morceau :** {titre.strip()}")
            st.write("**Fichiers :**")
            for fichier in fichiers:
                st.write(f"- {fichier.name}")
            st.write(f"**Utilisation de l'IA :** {'Oui' if ia_utilisee else 'Non'}")
            if ia_utilisee:
                st.write(
                    "**Étapes concernées :** "
                    + (", ".join(etapes_ia) if etapes_ia else "Aucune étape sélectionnée")
                )
            st.write(
                f"**Commentaire :** {commentaire.strip() or 'Aucun commentaire'}"
            )
            st.info("Ceci est un aperçu : aucun dépôt n'est enregistré.")
