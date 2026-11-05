# course-site-template

Template for password-protected course activity sites published on GitHub Pages. **Contains no course content.**

Each course gets two repos: a private `course-<CODE>-src` (sources, this template filled in) and a public `course-<CODE>` (encrypted output only), published at `https://fattaccioli.github.io/course-<CODE>/`.

To start a new course, copy this template, replace every `__PLACEHOLDER__` in `toc.yml` and `CLAUDE.md`, and follow the setup below. `templates/activity-starter.html` is the starting point for new activity pages.

## How it works

- Every `.html` file in `content/` is an activity. Each subfolder is a section of the index (`content/transport/` → "Transport en microfluidique").
- On every push to `main`, GitHub Actions runs `build.py`, which:
  1. builds `index.html` from the files' `<title>` and `<meta name="description">`, corrected by `toc.yml`;
  2. encrypts every HTML page, index included (AES-256-GCM, key derived from the password with PBKDF2-SHA256, 600 000 iterations);
  3. publishes the encrypted site on GitHub Pages.
- Students enter the password once. "Rester connecté" keeps them logged in on that device for `remember_days` (120 by default), across all pages.

## Adding an activity

1. Copy `templates/activity-starter.html` to `content/<section>/<name>.html`. Make sure it has a meaningful `<title>` and, ideally, a `<meta name="description" content="…">` in its `<head>`.
2. Commit and push. The page appears in the index with its own title.
3. To edit its entry (title, description, order, hide it), run `python build.py --sync-toc`. This appends an entry to `toc.yml`; edit it, commit and push.

`toc.yml` fields per page: `title`, `description`, `order` (smaller = higher), `hidden: true`. An entry with `url:` (and `section:`) adds an external link, e.g. a Moodle resource. Section names, descriptions and order are under `sections:`.

## Local preview

```bash
pip install -r requirements.txt
python build.py --preview                       # unencrypted, in _site/
python -m http.server -d _site 8000             # open http://localhost:8000
SITE_PASSWORD=test python build.py              # encrypted, to test the login page
```

## One-time setup

The readable sources must stay private; only encrypted files are ever public. Choose one:

**A. Single private repo (requires GitHub Pro, free for teachers via GitHub Education)**

1. Create the private repo `fattaccioli/course-<CODE>` and push this folder.
2. Settings → Pages → Source: **GitHub Actions**.
3. Settings → Secrets and variables → Actions → New repository secret: `SITE_PASSWORD`.
4. Push (or Actions → "Publier le site" → Run workflow).

**B. Two repos (works on a free account)**

1. Create the **private** repo `fattaccioli/course-<CODE>-src` (sources) and push this folder.
2. Create the **public**, empty repo `fattaccioli/course-<CODE>` (published site).
3. Create a fine-grained personal access token (Settings → Developer settings) limited to `course-<CODE>`, permission *Contents: read and write*.
4. In `course-<CODE>-src` → Settings → Secrets and variables → Actions:
   - secrets `SITE_PASSWORD` and `DEPLOY_TOKEN` (the token);
   - variable `DEPLOY_REPO` = `fattaccioli/course-<CODE>`.
5. Push once, then in `course-<CODE>` → Settings → Pages → Source: *Deploy from a branch*, branch `gh-pages`, folder `/`.

## Changing the password

Update the `SITE_PASSWORD` secret and re-run the workflow. Students who stayed logged in are asked for the new password at their next visit. Answers they typed in the activities are kept.

## Limits

- Anyone who has the password can share it. Suitable for course material, not for sensitive data.
- Students who have the password can read everything in a page once it is decrypted, including answer keys embedded in it.
- Only HTML is encrypted. PDFs, images and other files in `content/` are copied as-is and are public to anyone who knows their URL. Keep slides on Moodle, or embed images in the HTML.
- All pages share one domain, hence one browser storage: each activity must use its own `localStorage` key and include the course code, since all course sites share the origin `fattaccioli.github.io`.
- Pages that load external libraries (Pyodide, fonts) still need an internet connection.
