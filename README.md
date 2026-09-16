# Onshape Part Studio Merger (RM internal tool)

Combines several single-part Part Studios in an Onshape document (e.g. one
per McMaster-Carr import) into a single Part Studio, then cleans up after
itself — mirroring the manual "assembly, export, re-import" workaround, but
in one click.

## Running it via GitHub Codespaces (no local install needed)

If you don't want to install Python locally, push this folder to a GitHub
repo and run it in a Codespace instead — everything happens in the browser.

1. Create a new repo on GitHub (private is fine) and push this folder to it.
2. On the repo page: **Code** → **Codespaces** tab → **Create codespace on main**.
   Wait ~1 minute — it builds a container and runs `pip install -r requirements.txt`
   automatically (see `.devcontainer/devcontainer.json`).
3. Add your API key as a secret so you don't have to paste it every session:
   GitHub → your avatar → **Settings** → **Codespaces** → **Secrets** →
   **New secret**. Add `ONSHAPE_ACCESS_KEY` and `ONSHAPE_SECRET_KEY`, and
   allow them for this repository. Then **rebuild/reopen** the Codespace so
   it picks them up (or just start a fresh one).
4. In the Codespace's terminal (already open in the browser), run:
   ```bash
   python app.py
   ```
5. A popup (or the **Ports** tab) shows port 5050 forwarded — click it to
   open the app in a new browser tab.
6. When you're done, you can just close the tab. Next time you want to use
   the tool: reopen the same Codespace from **Code → Codespaces** on the
   repo page (don't create a new one each time), and run `python app.py`
   again — the secrets and dependencies are already there.

No local Python, no local install, nothing on this laptop.

## One-time setup (running it locally instead)

1. **Get an Onshape API key pair.**
   Go to https://dev-portal.onshape.com/keys → "Create new API key".
   Give it read/write access. You'll get an access key and a secret key —
   the secret is shown once, save it somewhere safe (a password manager,
   not this repo).

2. **Install dependencies** (Python 3.9+):
   ```bash
   cd onshape-merge-tool
   python3 -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set your API key as environment variables** (don't hardcode them in a file):
   ```bash
   export ONSHAPE_ACCESS_KEY="your_access_key"
   export ONSHAPE_SECRET_KEY="your_secret_key"
   ```
   On Windows (PowerShell): `$env:ONSHAPE_ACCESS_KEY="..."`

4. **Run it:**
   ```bash
   python app.py
   ```
   Then open http://localhost:5050 in your browser.

## Using it

1. Open your RM Onshape document, copy the URL from the address bar (it
   should look like `.../documents/<id>/w/<id>/e/<id>`), paste it in and
   click "Load Part Studios."
2. Check the boxes next to the loose single-part studios you want combined.
3. Type the name you want the merged Part Studio to end up with.
4. Leave "delete originals" checked if you only want to keep the merged
   result (this is the default — matches what you asked for). Uncheck it
   if you want to keep the source tabs around for a run or two while you
   trust the tool.
5. Click Merge. The log shows each step; when it says "Done," reload the
   Onshape document tab list to see the new combined Part Studio.

## What it does under the hood

1. Creates a scratch Assembly.
2. Inserts each selected Part Studio's parts into it (offset along X so
   bodies don't sit exactly on top of each other — this is cosmetic only,
   since the goal is a parts library, not a positioned physical assembly).
3. Exports that Assembly as STEP.
4. Re-imports the STEP with `flattenAssemblies=true`, which reproduces the
   Onshape import dialog's "combine into a single Part Studio" behavior —
   each solid becomes its own Part inside one new Part Studio.
5. Renames the new Part Studio to whatever you typed.
6. Deletes the scratch Assembly, and (if left checked) the original
   single-part Part Studios.

## One thing to double-check before you trust it on real work

`rename_element` in `onshape_client.py` is the one call in here I'm least
certain about — Onshape's endpoint for renaming an element isn't as
prominently documented as the others. Before running this on anything you
care about, open Onshape's live API explorer at
https://cad.onshape.com/glassworks/explorer, find the element-rename call,
and confirm the path/method match what's in the code. If it's different,
it's a one-line fix in `onshape_client.py`.

Everything else (list elements, create assembly, insert instance, export
translation, import translation, delete element) is based on Onshape's
published docs and forum-confirmed working examples.

## Scope note

This only automates the Onshape side. It assumes the McMaster parts are
already sitting in the document as individual Part Studios (however they
got there — McMaster's "Send to Onshape" button or a manual STEP import).
It doesn't touch McMaster's website.
