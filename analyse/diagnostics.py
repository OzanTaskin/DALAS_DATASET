"""Graphiques de contrôle : la collecte et les tables ont-elles l'air justes ?

Usage :
    python -m analyse.diagnostics    # écrit data/diagnostics/*.png (non versionné)

Chaque figure répond à une question de vérification :
01  les fichiers téléchargés ont-ils une taille stable d'une archive à l'autre (pas de page d'erreur,
    pas de fichier tronqué) ?
02  le lecteur extrait-il un nombre de lignes stable de chaque archive ?
03  les signalements officiels et les pénuries de la page ANSM racontent-ils la même histoire ?
04  le rapprochement vers l'ATC est-il aussi bon chaque année ?
05  les épisodes démarrent-ils à un rythme plausible dans chaque pays ?
06  les durées sont-elles plausibles (et combien sont négatives) ?
07  le marché historisé (BDPM) évolue-t-il sans sauts ?
08  quelles classes thérapeutiques portent les signalements, mois par mois ?
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

RACINE = Path(__file__).resolve().parent.parent
RAW, CLEAN = RACINE / "data" / "raw", RACINE / "data" / "clean"
SORTIE = RACINE / "data" / "diagnostics"

PAYS = {"FR": ("France", "#2a78d6"), "IT": ("Italie", "#eb6834"), "DE": ("Allemagne", "#1baf7a")}
BLEU, CRITIQUE = "#2a78d6", "#d03b3b"
TEXTE, TEXTE_SECONDAIRE, GRILLE, FOND = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
RAMPE = LinearSegmentedColormap.from_list("bleu", ["#f4f8fd", "#b7d3f6", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"])
MIO = 1_048_576

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": GRILLE, "axes.facecolor": FOND,
    "figure.facecolor": FOND, "axes.labelcolor": TEXTE_SECONDAIRE, "xtick.color": TEXTE_SECONDAIRE,
    "ytick.color": TEXTE_SECONDAIRE, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 9, "axes.titlecolor": TEXTE, "axes.titlelocation": "left", "lines.linewidth": 1.6,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRILLE, "grid.linewidth": 0.6,
    "xtick.major.size": 0, "ytick.major.size": 0,
})
lire = lambda nom: pd.read_parquet(CLEAN / f"{nom}.parquet")


def axe_dates(ax):
    debut, fin = [matplotlib.dates.num2date(x) for x in ax.get_xlim()]
    court = (fin - debut).days < 3 * 365
    long = (fin - debut).days > 8 * 365
    ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=(1, 7)) if court
                               else matplotlib.dates.YearLocator(2 if long else 1))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%Y" if court else "%Y"))


def titre_figure(fig, texte, sous_titre):
    fig.suptitle(texte, x=0.01, y=1 - 0.08 / fig.get_figheight(), va="top", ha="left", fontsize=11, color=TEXTE, fontweight="bold")
    fig.text(0.01, 1 - 0.42 / fig.get_figheight(), sous_titre, ha="left", fontsize=8, color=TEXTE_SECONDAIRE)


def enregistrer(fig, nom):
    fig.savefig(SORTIE / nom, dpi=150)
    plt.close(fig)
    print(f"  {nom}")


def tailles_archives():
    manifeste = pd.read_csv(RAW / "manifeste.csv").drop_duplicates("fichier", keep="last")
    wb = manifeste[manifeste["fichier"].str.startswith("wayback/")].copy()
    wb["cible"] = wb["fichier"].str.split("/").str[1]
    wb["date"] = pd.to_datetime(wb["fichier"].str.split("/").str[2].str[:8], format="%Y%m%d")
    cibles = [("ansm_disponibilites", "Page ANSM (HTML)"), ("aifa_carenti", "Liste italienne (CSV)"),
              ("bfarm_lieferengpaesse", "Liste allemande (CSV)"), ("bdpm_cis", "BDPM, médicaments"),
              ("bdpm_cip", "BDPM, boîtes"), ("bdpm_gener", "BDPM, génériques")]
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.6))
    for ax, (cible, nom) in zip(axes.flat, cibles):
        d = wb[wb["cible"] == cible].sort_values("date")
        ax.plot(d["date"], d["octets"] / 1e6, color=BLEU, marker="o", markersize=3)
        if cible.startswith("bdpm"):
            tronque = d[d["octets"] == MIO]
            ax.scatter(tronque["date"], tronque["octets"] / 1e6, color=CRITIQUE, s=22, zorder=3,
                       label=f"tronquée à 1 Mio ({len(tronque)})")
            ax.axhline(MIO / 1e6, color=TEXTE_SECONDAIRE, linestyle=":", linewidth=0.8)
            ax.legend(frameon=False, loc="lower right", fontsize=7)
        ax.set_title(f"{nom} · {len(d)} archives")
        ax.set_ylim(0, None)
        axe_dates(ax)
        ax.set_ylabel("Mo")
    titre_figure(fig, "1. Taille de chaque archive téléchargée",
                 "Une chute brutale = page d'erreur ou fichier tronqué. Les archives BDPM coupées à 1 Mio sont écartées au nettoyage.")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    enregistrer(fig, "01_tailles_archives.png")


def lignes_par_photo():
    ansm = lire("ansm_observations").groupby("date_photo").size()
    europe = lire("europe_observations").groupby(["pays", "date_photo"]).size()
    series = {"FR": ansm, "IT": europe["IT"], "DE": europe["DE"]}
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    for ax, (pays, s) in zip(axes, series.items()):
        nom, couleur = PAYS[pays]
        ax.plot(s.index, s.values, color=couleur, marker="o", markersize=3)
        ax.set_ylim(0, s.max() * 1.15)
        ax.set_title(f"{nom} · {len(s)} photos, {s.min()} à {s.max()} lignes")
        axe_dates(ax)
    axes[0].set_ylabel("lignes lues")
    titre_figure(fig, "2. Lignes extraites de chaque photo",
                 "Doit suivre la taille des fichiers (figure 1) : une photo à 0 ou en chute isolée = lecteur cassé sur ce format.")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    enregistrer(fig, "02_lignes_par_photo.png")


def signalements_et_page():
    p = lire("penuries_fr_mensuel")
    mois = p.groupby("mois")[["nb_signalements", "nb_nouvelles_penuries_affichees"]].sum(min_count=1)
    fig, axes = plt.subplots(2, 1, figsize=(11, 5), sharex=True)
    for ax, (colonne, nom) in zip(axes, [("nb_signalements", "Signalements officiels ANSM, par mois"),
                                         ("nb_nouvelles_penuries_affichees", "Nouvelles pénuries sur la page ANSM, par mois")]):
        s = mois[colonne].dropna()
        ax.axvspan(pd.Timestamp("2022-09-01"), pd.Timestamp("2023-03-31"), color=GRILLE, linewidth=0, zorder=0)
        ax.bar(s.index, s.values, width=24, color=BLEU, zorder=2)
        total = f"{int(s.sum()):,}".replace(",", " ")
        ax.set_title(f"{nom} · total {total}")
        ax.set_ylim(0, s.max() * 1.18)
    axes[0].text(pd.Timestamp("2022-12-15"), axes[0].get_ylim()[1] * 0.97, "crise des antibiotiques",
                 ha="center", va="top", color=TEXTE_SECONDAIRE, fontsize=7, zorder=3,
                 bbox={"facecolor": FOND, "edgecolor": "none", "pad": 1})
    titre_figure(fig, "3. Les deux sources françaises racontent-elles la même histoire ?",
                 "Mêmes tendances attendues (pic de l'hiver 2022-2023), à des échelles différentes : la page ne montre qu'une partie des signalements.")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    enregistrer(fig, "03_signalements_et_page.png")


def couverture_atc():
    s = lire("ansm_signalements")
    methodes = ["cip", "cip_open_medic", "nom", "substance", "marque"]
    parts = (s.assign(m=s["methode_rapprochement"].astype("object").fillna("sans ATC"))
             .groupby("annee")["m"].value_counts(normalize=True).unstack(fill_value=0))
    couleurs = ["#0d366b", "#1c5cab", "#3987e5", "#86b6ef", "#cde2fb", CRITIQUE]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    bas = np.zeros(len(parts))
    for m, c in zip(methodes + ["sans ATC"], couleurs):
        v = parts.get(m, pd.Series(0, index=parts.index)).to_numpy() * 100
        ax.bar(parts.index, v, bottom=bas, color=c, label=m, width=0.7, edgecolor=FOND, linewidth=1)
        bas += v
    for x, sans in zip(parts.index, parts.get("sans ATC", 0) * 100):
        ax.text(x, 101, f"{sans:.1f} % sans ATC", ha="center", fontsize=7, color=TEXTE_SECONDAIRE)
    ax.set_ylim(0, 108)
    ax.set_ylabel("% des signalements")
    ax.legend(frameon=False, ncol=6, loc="upper left", bbox_to_anchor=(0, -0.08), fontsize=7)
    titre_figure(fig, "4. Comment chaque signalement a reçu son code ATC",
                 "Avant 2022, pas de code CIP : on passe par le nom. La part sans ATC doit rester faible chaque année.")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    enregistrer(fig, "04_couverture_atc.png")


def debuts_episodes():
    e = lire("shortage_events")
    e = e[(e["type_episode"] == "penurie") & ~e["censure_gauche"].astype(bool)]
    fig, axes = plt.subplots(3, 1, figsize=(11, 5.6), sharex=True)
    for ax, pays in zip(axes, ["FR", "IT", "DE"]):
        nom, couleur = PAYS[pays]
        s = e[e["pays"] == pays].set_index("publication").resample("MS").size()
        ax.bar(s.index, s.values, width=24, color=couleur)
        ax.set_title(f"{nom} · {int(s.sum())} pénuries publiées (hors pénuries déjà en cours à la 1re archive)")
    titre_figure(fig, "5. Nouvelles pénuries par mois de publication",
                 "Un pic isolé = souvent une archive après un trou (plusieurs mois d'apparitions comptés d'un coup), pas forcément une vraie vague.")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    enregistrer(fig, "05_debuts_episodes.png")


def durees():
    e = lire("shortage_events")
    e = e[(e["type_episode"] == "penurie") & ~e["en_cours"] & ~e["censure_gauche"].astype(bool)]
    e = e.assign(duree=(e["fin"] - e["debut"]).dt.days).dropna(subset=["duree"])
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharey=False)
    bornes = np.arange(-400, 1500, 30)
    for ax, pays in zip(axes, ["FR", "IT", "DE"]):
        nom, couleur = PAYS[pays]
        d = e[e["pays"] == pays]["duree"].clip(-399, 1499)
        ax.hist(d[d >= 0], bins=bornes, color=couleur, edgecolor=FOND, linewidth=0.5)
        ax.hist(d[d < 0], bins=bornes, color=CRITIQUE, edgecolor=FOND, linewidth=0.5)
        neg = (d < 0).sum()
        ax.set_title(f"{nom} · médiane {d.median():.0f} j · {neg} négatives ({neg / len(d):.0%})")
        ax.set_xlabel("durée (jours, coupée à 1 500)")
    axes[0].set_ylabel("épisodes terminés")
    titre_figure(fig, "6. Durée des pénuries terminées",
                 "En rouge : fin avant le début (pénurie annoncée puis retirée, ou plus courte que l'écart entre deux archives).")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    enregistrer(fig, "06_durees.png")


def bdpm_historique():
    tables = [("bdpm_specialites_historique", "commercialise", "Médicaments (CIS) commercialisés"),
              ("bdpm_presentations_historique", "commercialisee", "Boîtes (CIP13) commercialisées")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2))
    for ax, (table, colonne, nom) in zip(axes, tables):
        h = lire(table)
        dates = pd.Index(sorted(h["valid_from"].unique()))
        fin = h["valid_to"].fillna(pd.Timestamp("2100-01-01"))
        n = [int(((h["valid_from"] <= d) & (fin > d) & h[colonne].astype(bool)).sum()) for d in dates]
        ax.plot(dates, n, color=BLEU, marker="o", markersize=3, drawstyle="steps-post")
        ax.set_ylim(0, max(n) * 1.15)
        ax.set_title(f"{nom} · {len(dates)} versions")
    titre_figure(fig, "7. Le marché français reconstruit dans le temps (BDPM historisée)",
                 "Doit être lisse : un saut = photo incomplète ou changement de format. Entre deux points, la dernière photo complète fait foi.")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    enregistrer(fig, "07_bdpm_historique.png")


def heatmap_classes():
    p = lire("penuries_fr_mensuel").dropna(subset=["nb_signalements"])
    atc = lire("atc").drop_duplicates("atc2").set_index("atc2")["libelle_atc2"].str.capitalize()
    p = p.assign(atc2=p["atc5"].str[:3])
    m = p.groupby(["atc2", "mois"])["nb_signalements"].sum().unstack(fill_value=0)
    m = m.loc[m.sum(axis=1).nlargest(15).index]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    image = ax.imshow(m.to_numpy(dtype=float), aspect="auto", cmap=RAMPE, interpolation="nearest")
    ax.set_yticks(range(len(m)), [f"{c} {str(atc.get(c, ''))[:38]}" for c in m.index], fontsize=7)
    annees = [i for i, d in enumerate(m.columns) if d.month == 1]
    ax.set_xticks(annees, [m.columns[i].year for i in annees])
    ax.grid(False)
    barre = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.01)
    barre.set_label("signalements dans le mois", color=TEXTE_SECONDAIRE)
    barre.outline.set_visible(False)
    titre_figure(fig, "8. Signalements par classe thérapeutique (ATC2) et par mois, 15 classes les plus touchées",
                 "Une ligne vide sur une période = classe perdue au rapprochement ; une colonne vide = mois manquant dans les classeurs.")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.6 / fig.get_figheight()))
    enregistrer(fig, "08_classes_par_mois.png")


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    for figure in (tailles_archives, lignes_par_photo, signalements_et_page, couverture_atc,
                   debuts_episodes, durees, bdpm_historique, heatmap_classes):
        figure()
    print(f"Figures écrites dans {SORTIE.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
