"""Outils communs à la collecte : session HTTP, téléchargement et manifeste.

Règle de la couche brute : les octets reçus sont écrits tels quels, sans
nettoyage ni réencodage. Chaque fichier est tracé dans data/raw/manifeste.csv.
"""
import csv
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

RACINE = Path(__file__).resolve().parent.parent
RAW = RACINE / "data" / "raw"
MANIFESTE = RAW / "manifeste.csv"
CHAMPS = ["source", "fichier", "url", "collecte_utc", "http", "type_contenu", "octets", "sha256"]

# Certains sites officiels (ANSM) refusent les clients sans User-Agent de navigateur.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128 Safari/537.36 (projet etudiant DALAS)"
)


def creer_session():
    """Session HTTP avec relances automatiques (erreurs serveur, limitation de débit)."""
    relances = Retry(
        total=6,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=relances))
    session.mount("http://", HTTPAdapter(max_retries=relances))
    session.headers["User-Agent"] = USER_AGENT
    return session


def sha256(contenu):
    return hashlib.sha256(contenu).hexdigest()


# Les téléchargements parallèles écrivent dans le même manifeste : un seul à la fois.
_verrou_manifeste = threading.Lock()


def ajouter_au_manifeste(ligne):
    with _verrou_manifeste:
        nouveau = not MANIFESTE.exists()
        MANIFESTE.parent.mkdir(parents=True, exist_ok=True)
        with MANIFESTE.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CHAMPS)
            if nouveau:
                writer.writeheader()
            writer.writerow(ligne)


def lire_manifeste():
    if not MANIFESTE.exists():
        return []
    with MANIFESTE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def telecharger(session, url, destination, source, timeout=300, valider=None):
    """Télécharge `url` vers `destination` (chemin relatif à data/raw).

    Un fichier déjà présent n'est pas retéléchargé : la collecte peut être
    relancée après une interruption sans tout refaire.
    `valider(contenu) -> bool` permet de refuser une réponse HTTP 200 qui n'est
    pas le fichier attendu (page d'erreur) : elle n'est alors pas enregistrée.
    Renvoie le chemin du fichier, ou None en cas d'échec.
    """
    chemin = RAW / destination
    if chemin.exists():
        return chemin

    try:
        reponse = session.get(url, timeout=timeout)
        reponse.raise_for_status()
    except requests.RequestException as erreur:
        print(f"  ÉCHEC {url} : {erreur}")
        return None
    if valider is not None and not valider(reponse.content):
        print(f"  ÉCHEC {url} : contenu inattendu ({reponse.content[:80]!r})")
        return None
    return enregistrer(reponse, destination, source)


def enregistrer(reponse, destination, source):
    """Écrit le contenu d'une réponse HTTP dans data/raw/<destination> et le trace."""
    chemin = RAW / destination
    # Le manifeste est écrit avant le fichier final : un fichier présent est toujours tracé.
    # (Une interruption entre les deux laisse au pire une ligne sans fichier, retéléchargé ensuite.)
    ajouter_au_manifeste({
        "source": source,
        "fichier": str(chemin.relative_to(RAW)),
        "url": reponse.url,
        "collecte_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "http": reponse.status_code,
        "type_contenu": reponse.headers.get("Content-Type", ""),
        "octets": len(reponse.content),
        "sha256": sha256(reponse.content),
    })
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".part")
    temporaire.write_bytes(reponse.content)
    temporaire.rename(chemin)
    return chemin
