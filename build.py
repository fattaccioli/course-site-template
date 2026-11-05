#!/usr/bin/env python3
"""
Construit le site du cours à partir du dossier content/.

  python build.py --preview        site non chiffré dans _site/, pour vérifier en local
  python build.py                  site chiffré (mot de passe lu dans la variable SITE_PASSWORD)
  python build.py --sync-toc       ajoute à toc.yml une entrée modifiable pour chaque nouvelle page

Chaque page HTML (y compris l'index) est chiffrée en AES-256-GCM avec une clé dérivée
du mot de passe par PBKDF2-SHA256, puis remplacée par une page de connexion qui la
déchiffre dans le navigateur (Web Crypto). Les fichiers non HTML sont copiés tels quels
et ne sont PAS protégés.
"""
import argparse, base64, datetime as dt, html, json, os, re, shutil, subprocess, sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CONTENT, OUT, TEMPLATES = ROOT / "content", ROOT / "_site", ROOT / "templates"
TOC = ROOT / "toc.yml"
ITERATIONS = 600_000


# ---------------------------------------------------------------- lecture
def load_toc():
    data = yaml.safe_load(TOC.read_text(encoding="utf-8")) if TOC.exists() else {}
    data = data or {}
    data.setdefault("site", {}); data.setdefault("sections", {}); data.setdefault("pages", {})
    data["sections"] = data["sections"] or {}; data["pages"] = data["pages"] or {}
    return data


def meta_of(path):
    """Titre et description lus dans le <head> de la page."""
    s = path.read_text(encoding="utf-8", errors="replace")[:20000]
    t = re.search(r"<title[^>]*>(.*?)</title>", s, re.S | re.I)
    d = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', s, re.S | re.I)
    clean = lambda x: html.unescape(re.sub(r"\s+", " ", x)).strip()
    return (clean(t.group(1)) if t else path.stem.replace("-", " ").capitalize(),
            clean(d.group(1)) if d else "")


def last_modified(path):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", str(path)], cwd=ROOT,
                             capture_output=True, text=True, timeout=10).stdout.strip()
        if out:
            return dt.datetime.fromisoformat(out)
    except Exception:
        pass
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)


def collect(toc):
    """Liste des pages, fusion des informations lues dans les fichiers et des entrées de toc.yml."""
    pages = []
    for f in sorted(CONTENT.rglob("*.html")):
        rel = f.relative_to(CONTENT).as_posix()
        if any(part.startswith((".", "_")) for part in f.relative_to(CONTENT).parts):
            continue
        title, desc = meta_of(f)
        e = toc["pages"].get(rel) or {}
        pages.append({
            "rel": rel, "href": rel,
            "section": rel.split("/")[0] if "/" in rel else "",
            "title": e.get("title", title), "description": e.get("description", desc),
            "order": e.get("order", 1000), "hidden": bool(e.get("hidden", False)),
            "date": last_modified(f), "external": False,
        })
    for key, e in toc["pages"].items():  # liens externes déclarés dans toc.yml
        if e and e.get("url"):
            pages.append({"rel": key, "href": e["url"], "section": e.get("section", ""),
                          "title": e.get("title", key), "description": e.get("description", ""),
                          "order": e.get("order", 1000), "hidden": bool(e.get("hidden", False)),
                          "date": None, "external": True})
    return pages


# ---------------------------------------------------------------- index
def render_index(toc, pages):
    site, sections = toc["site"], toc["sections"]
    now = dt.datetime.now(dt.timezone.utc)
    new_days = site.get("new_days", 14)
    groups = {}
    for p in pages:
        if not p["hidden"]:
            groups.setdefault(p["section"], []).append(p)
    def sec_key(name):
        s = sections.get(name) or {}
        return (s.get("order", 1000), (s.get("title") or name).lower())
    blocks = []
    for name in sorted(groups, key=sec_key):
        s = sections.get(name) or {}
        title = s.get("title") or (name.replace("-", " ").capitalize() if name else "Général")
        items = []
        for p in sorted(groups[name], key=lambda p: (p["order"], p["title"].lower())):
            badge, date = "", ""
            if p["date"]:
                if (now - p["date"]).days < new_days:
                    badge = '<span class="badge">Nouveau</span>'
                date = '<span class="date">Mis à jour le ' + p["date"].strftime("%d/%m/%Y") + "</span>"
            ext = ' target="_blank" rel="noopener"' if p["external"] else ""
            kind = '<span class="kind">Lien externe</span>' if p["external"] else ""
            items.append(
                f'<li><a class="card" href="{html.escape(p["href"])}"{ext}>'
                f'<span class="card-title">{html.escape(p["title"])}{badge}</span>'
                + (f'<span class="card-desc">{html.escape(p["description"])}</span>' if p["description"] else "")
                + f'<span class="card-meta">{kind}{date}</span></a></li>')
        desc = f'<p class="sec-desc">{html.escape(s["description"])}</p>' if s.get("description") else ""
        blocks.append(f'<section class="sec"><h2>{html.escape(title)}</h2>{desc}<ul class="cards">{"".join(items)}</ul></section>')
    link = site.get("course_link") or site.get("moodle")
    moodle = (f'<a class="moodle" href="{html.escape(link)}" target="_blank" rel="noopener">'
              f'{html.escape(site.get("course_link_label", "Page Moodle du cours"))}</a>' if link else "")
    tpl = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    return (tpl.replace("{{TITLE}}", html.escape(site.get("title", "Cours")))
               .replace("{{SUBTITLE}}", html.escape(site.get("subtitle", "")))
               .replace("{{MOODLE}}", moodle)
               .replace("{{EYEBROW}}", html.escape(site.get("eyebrow", "")))
               .replace("{{SECTIONS}}", "\n".join(blocks) or '<p class="empty">Aucune activité pour le moment.</p>')
               .replace("{{SALT}}", json.dumps(site.get("salt", "site")))
               .replace("{{BUILT}}", now.astimezone().strftime("%d/%m/%Y à %H:%M")))


# ---------------------------------------------------------------- chiffrement
def derive_key(password, salt):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt.encode(), iterations=ITERATIONS)
    return kdf.derive(password.encode("utf-8"))


def encrypt_page(raw_html, key, site, depth):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, raw_html.encode("utf-8"), None)
    payload = {"salt": site.get("salt", "site"), "iter": ITERATIONS,
               "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode(),
               "days": site.get("remember_days", 120), "home": "../" * depth or "./"}
    tpl = (TEMPLATES / "login.html").read_text(encoding="utf-8")
    hint = site.get("login_hint", "Entrez le mot de passe communiqué en cours.")
    return (tpl.replace("{{TITLE}}", html.escape(site.get("title", "Cours")))
               .replace("{{LOGIN_HINT}}", html.escape(hint))
               .replace("{{PAYLOAD}}", json.dumps(payload)))


# ---------------------------------------------------------------- toc.yml
def sync_toc(toc, pages):
    missing = [p for p in pages if not p["external"] and p["rel"] not in toc["pages"]]
    if not missing:
        print("toc.yml est à jour : aucune nouvelle page.")
        return
    text = TOC.read_text(encoding="utf-8").rstrip("\n") + "\n"
    text = re.sub(r"^pages:\s*\{\s*\}\s*$", "pages:", text, flags=re.M)
    if not re.search(r"^pages:", text, re.M):
        text += "\npages:\n"
    for p in missing:
        text += (f'\n  {p["rel"]}:\n    title: {json.dumps(p["title"], ensure_ascii=False)}\n'
                 f'    description: {json.dumps(p["description"], ensure_ascii=False)}\n    order: 100\n')
    TOC.write_text(text, encoding="utf-8")
    print("Entrées ajoutées à toc.yml :\n  " + "\n  ".join(p["rel"] for p in missing))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true", help="ne pas chiffrer (vérification en local)")
    ap.add_argument("--sync-toc", action="store_true", help="ajouter les nouvelles pages à toc.yml et s'arrêter")
    args = ap.parse_args()

    toc = load_toc()
    pages = collect(toc)
    if args.sync_toc:
        return sync_toc(toc, pages)

    password = os.environ.get("SITE_PASSWORD", "")
    if not args.preview and not password:
        sys.exit("Erreur : SITE_PASSWORD n'est pas défini. Utilisez --preview pour un aperçu non chiffré.")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / ".nojekyll").write_text("")
    key = None if args.preview else derive_key(password, toc["site"].get("salt", "site"))

    def write_html(rel, text):
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        depth = rel.count("/")
        dest.write_text(text if key is None else encrypt_page(text, key, toc["site"], depth), encoding="utf-8")

    unprotected = []
    for f in sorted(CONTENT.rglob("*")):
        rel_parts = f.relative_to(CONTENT).parts
        if f.is_dir() or any(x.startswith((".", "_")) for x in rel_parts):
            continue
        rel = f.relative_to(CONTENT).as_posix()
        if f.suffix.lower() == ".html":
            write_html(rel, f.read_text(encoding="utf-8"))
        else:
            (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, OUT / rel)
            unprotected.append(rel)
    write_html("index.html", render_index(toc, pages))

    listed = [p for p in pages if not p["hidden"]]
    print(f"Site construit dans _site/ : {len(listed)} entrée(s) dans l'index, "
          f"{'NON chiffré (aperçu)' if key is None else 'chiffré'}.")
    for p in pages:
        if not p["external"] and p["rel"] not in toc["pages"]:
            print(f"  nouvelle page sans entrée dans toc.yml (titre lu dans le fichier) : {p['rel']}")
    if unprotected:
        print("  Attention, fichiers copiés sans protection : " + ", ".join(unprotected))


if __name__ == "__main__":
    main()
