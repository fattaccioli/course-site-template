# CLAUDE.md — __REPO_NAME__

Password-protected activity site for the course **__COURSE_CODE__ · __COURSE_TITLE__** (__EYEBROW__), taught by Jacques Fattaccioli. Published at https://fattaccioli.github.io/__REPO_NAME__/ via GitHub Actions, from the private source repo `fattaccioli/__REPO_NAME__-src`.

## Audience and language

- Students: __AUDIENCE__. Connect new material to what they already know, and do not explain standard concepts in a way that patronises them.
- **Student-facing content is in __LANGUAGE__**, in a rigorous scientific register. When lecture material is in another language, give the original term in parentheses the first time a key term appears.
- Code comments in activity pages are in French. Repo files (this file, README, build.py docstrings) stay as they are.

## Repository layout

```
content/<section>/<activity>.html   activities; one subfolder = one section of the index
toc.yml                             site settings + optional overrides of index entries
templates/index.html                index page template ({{PLACEHOLDERS}} filled by build.py)
templates/login.html                password page wrapping every encrypted page
build.py                            builds _site/: index, AES-GCM encryption, copies other files
.github/workflows/deploy.yml        builds and deploys on push to main
```

`_site/` is a build output: never edit or commit it.

## Commands

```bash
pip install -r requirements.txt
python build.py --preview                 # unencrypted build in _site/
python -m http.server -d _site 8000       # serve it (crypto.subtle needs http://localhost or https)
SITE_PASSWORD=test python build.py        # encrypted build, to test the login flow
python build.py --sync-toc                # append toc.yml entries for pages that have none
```

Always run `python build.py --preview` after a change and check that it reports no error.

## Adding or changing an activity

1. Create `content/<section>/<kebab-case-name>.html`. Reuse an existing section folder when the topic fits; a new folder creates a new section.
2. The file must be a **complete, self-contained HTML document**: `<!doctype html>`, `<meta charset="utf-8">`, viewport meta, a meaningful French `<title>` and a `<meta name="description" content="…">` (one sentence; it becomes the index card text). Inline all CSS and JS; external scripts only from pinned CDN URLs (e.g. `https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js`).
3. Run `python build.py --sync-toc`, then edit the new entry in `toc.yml` if the title/description/order need adjusting. Add a `sections:` entry (title, description, order) when you create a new section.
4. Run `python build.py --preview` and open the page through the local server to check it.
5. Commit with a clear message. Pushing to `main` publishes.

### Conventions for activity pages

- **Visual identity**: reuse the design tokens of `templates/activity-starter.html` (colours `--bg --surface --fg --muted --line --accent --soft --dye`, fonts Bricolage Grotesque / Instrument Sans / JetBrains Mono, light and dark themes via `prefers-color-scheme`). New pages should look like they belong to the same site. Must work at phone width.
- **Browser storage**: all pages share one origin. Any `localStorage` key must be unique and namespaced by activity, e.g. `__COURSE_CODE__-<section>-<activity>-reponses-v1` (all course sites share the origin fattaccioli.github.io, so the course code must be in the key). Never use generic keys, never call `localStorage.clear()`, and never touch keys starting with `site-key:` (login).
- **Starting point**: copy `templates/activity-starter.html` (same look, answer system, one Pyodide simulation) and replace its placeholder content.
- **Answer blocks**: the starter contains a reusable answer system (the last `<script>` block: `Q = {…}` spec, `build()`, `check()`, export). For new exercise pages, copy and adapt it rather than writing a new one. Part types: `num` (with `lo`/`hi` tolerance and optional `alt` for classic wrong answers with a targeted message), `mcq` (`ok` indices, `multi: true` for checkboxes), `select` (matching rows), `text`. Predictions (`pred: true`) have no correction. Keep `SHOW_FEEDBACK` as a single switch at the top.
- **Numerical answers**: verify every expected value and tolerance by actually computing it (run Python), and make the explanation (`why`) consistent with it. Give tolerances wide enough for reasonable rounding and for the common convention differences (e.g. L²/D vs L²/2D).
- **Simulations**: in-browser Python with Pyodide + numpy + matplotlib, code visible and editable by students in a `<textarea>`, one `simulate_<name>(p)` function returning `(fig, readouts)`. Test the Python code locally with plain CPython before embedding it. Avoid NumPy functions removed in NumPy 2 (`np.trapz` → manual trapezoid or `np.trapezoid`).
- **Pedagogy**: activities are meant to be done *before* class. Order inside a page: reading/video → kitchen experiment → order-of-magnitude calculation → written prediction → simulation to check. Simulations come after the calculation they verify, never before.
- Do not include lecture slides or their figures unless asked.

## Things not to do

- Do not commit the password, a `.env` file, or anything decrypted from `_site/`. The password lives only in the GitHub secret `SITE_PASSWORD`.
- Do not change `site.salt` in `toc.yml` (it logs everyone out) or `ITERATIONS` in `build.py` without being asked.
- Do not put PDFs, images or data files in `content/` expecting them to be protected: only `.html` is encrypted, everything else is public by URL. Embed small images as data URIs inside the HTML; keep slides on Moodle (`site.course_link` in `toc.yml`).
- Do not modify `templates/login.html` or the encryption code in `build.py` unless asked; if you do, test the full flow (wrong password rejected, right password opens, "Rester connecté" works across pages, "Se déconnecter" works) with an encrypted build in a real browser (Playwright is fine).
- Do not add a static site generator (Jekyll, Hugo…): the build is deliberately a single Python script.

## Deployment

The workflow supports two setups, selected automatically:
- **single repo** (private with GitHub Pro): Pages source = GitHub Actions; needs secret `SITE_PASSWORD`;
- **two repos** (private sources `__REPO_NAME__-src`, public `__REPO_NAME__`): also needs repo variable `DEPLOY_REPO` and secret `DEPLOY_TOKEN`; the public repo serves branch `gh-pages`.

After a push, check the Actions run. If it fails on "SITE_PASSWORD n'est pas défini", the secret is missing.

## Related

- Public course description: https://fattaccioli.github.io/teaching/ (Jekyll site, repo `fattaccioli/fattaccioli.github.io`). Do not modify it from this repo.
- Course page: __COURSE_LINK__
- Built from the template `fattaccioli/course-site-template`. Fixes to build.py or templates/ should also go to the template.
