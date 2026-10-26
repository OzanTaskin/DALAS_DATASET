"""Figures du rapport TME4 (rapport_tme4/figures/*.pdf), à partir de data/clean.

Usage :
    python -m analyse.figures_tme4

Couleurs : trois premiers emplacements de la palette catégorielle de référence
(validés deux à deux, y compris pour les daltoniens) ; une couleur par pays, toujours la même.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
CLEAN = RACINE / "data" / "clean"
SORTIE = RACINE / "rapport_tme4" / "figures"

COULEURS = {"FR": "#2a78d6", "IT": "#eb6834", "DE": "#1baf7a"}
NOMS = {"FR": "France (ANSM)", "IT": "Italie (AIFA)", "DE": "Allemagne (BfArM)"}
TEXTE, TEXTE_SECONDAIRE, GRILLE = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": GRILLE,
    "axes.labelcolor": TEXTE_SECONDAIRE, "xtick.color": TEXTE_SECONDAIRE,
    "ytick.color": TEXTE_SECONDAIRE, "axes.spines.top": False, "axes.spines.right": False,
})


TROU = pd.Timedelta(days=100)  # au-delà, deux archives successives ne sont pas reliées


def penuries_par_photo():
    """Nombre de pénuries listées dans chaque archive : mesure directe, sans reconstruction d'épisodes."""
    ansm = pd.read_parquet(CLEAN / "ansm_observations.parquet")
    ansm = ansm[ansm["statut"].isin(["rupture", "tension", "risque_rupture"])].assign(pays="FR")
    europe = pd.read_parquet(CLEAN / "europe_observations.parquet")
    europe = europe[~europe["raison"].fillna("").str.contains("Cessata commercializzazione definitiva")]
    france = ansm.groupby(["pays", "date_photo"]).size()
    autres = europe.groupby(["pays", "date_photo"])["id_episode"].nunique()
    return pd.concat([france, autres]).rename("n").reset_index()


def figure_evolution():
    serie = penuries_par_photo()
    debut, fin = serie["date_photo"].min(), serie["date_photo"].max()
    # Petits multiples : les volumes diffèrent d'un facteur 10 entre pays, chaque panneau a son échelle.
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.1), sharex=True)
    for ax, pays in zip(axes, ["FR", "IT", "DE"]):
        s = serie[serie["pays"] == pays].sort_values("date_photo").reset_index(drop=True)
        ax.set_ylim(0, s["n"].max() * 1.18)
        # Périodes sans archive : grisées, la courbe y est interrompue.
        premiere = s["date_photo"].iloc[0]
        trous = [(debut, premiere)] if premiere - debut > TROU else []
        trous += [(a, b) for a, b in zip(s["date_photo"], s["date_photo"].iloc[1:]) if b - a > TROU]
        for a, b in trous:
            ax.axvspan(a, b, color=GRILLE, alpha=0.7, linewidth=0)
        if trous:
            a, b = max(trous, key=lambda t: t[1] - t[0])
            ax.text(a + (b - a) / 2, ax.get_ylim()[1] * 0.04, "pas\nd'archive", ha="center",
                    color=TEXTE_SECONDAIRE, fontsize=6, va="bottom")
        segment = (s["date_photo"].diff() > TROU).cumsum()
        for _, morceau in s.groupby(segment):
            # Un point par archive : une archive isolée entre deux trous (fréquent en Allemagne, archives
            # espacées de 3 à 4 mois) ne forme pas de ligne et serait sinon invisible.
            ax.plot(morceau["date_photo"], morceau["n"], color=COULEURS[pays], linewidth=2,
                    marker="o", markersize=2.5)
        ax.set_title(NOMS[pays], color=TEXTE, fontsize=8.5, loc="left")
        ax.grid(axis="y", color=GRILLE, linewidth=0.6)
        ax.tick_params(length=0)
        ax.set_xlim(debut, fin)
        dernier = s.iloc[-1]
        ax.annotate(f"{dernier['n']:,}".replace(",", " "), (dernier["date_photo"], dernier["n"]),
                    xytext=(3, 0), textcoords="offset points", fontsize=7, color=TEXTE, va="center",
                    annotation_clip=False)
        ax.xaxis.set_major_locator(matplotlib.dates.YearLocator(2))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
    axes[0].set_ylabel("pénuries listées")
    fig.tight_layout(w_pad=2)
    fig.savefig(SORTIE / "evolution_penuries.pdf")
    plt.close(fig)


def figure_classes(evenements, atc):
    france = evenements[evenements["pays"] == "FR"].dropna(subset=["atc5"])
    libelles = atc.drop_duplicates("atc2").set_index("atc2")["libelle_atc2"].str.capitalize()
    top = france["atc5"].str[:3].value_counts().head(10).sort_values()
    noms = [f"{code} {libelles.get(code, '')}" for code in top.index]

    fig, ax = plt.subplots(figsize=(3.6, 2.5))
    ax.barh(noms, top.values, color=COULEURS["FR"], height=0.7)
    for y, n in enumerate(top.values):
        ax.text(n + 2, y, str(n), va="center", fontsize=7, color=TEXTE)
    ax.set_xlabel("épisodes de pénurie, 2021-2026")
    ax.tick_params(length=0, labelsize=7)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, top.max() * 1.15)
    ax.grid(axis="x", color=GRILLE, linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(SORTIE / "classes_france.pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    evenements = pd.read_parquet(CLEAN / "shortage_events.parquet")
    evenements = evenements[evenements["type_episode"] == "penurie"]
    atc = pd.read_parquet(CLEAN / "atc.parquet")
    figure_evolution()
    figure_classes(evenements, atc)
    print(f"Figures écrites dans {SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
