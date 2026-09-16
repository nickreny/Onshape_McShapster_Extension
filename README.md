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
   **New secret**. Add `ACCESS_KEY_ONSHAPE` and `SECRET_KEY_ONSHAPE`, and
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
   export ACCESS_KEY_ONSHAPE="your_access_key"
   export SECRET_KEY_ONSHAPE="your_secret_key"
   ```
   On Windows (PowerShell): `$env:ACCESS_KEY_ONSHAPE="..."`

4. **Run it:**
   ```bash
   python app.py
   ```
   Then open http://localhost:5050 in your browser.

## Using it

1. Download the STEP file(s) for your McMaster parts as usual (no change there).
2. Open your RM Onshape document, copy the URL from the address bar (it
   should look like `.../documents/<id>/w/<id>/e/<id>`), paste it in and
   click "Load Part Studios."
3. In the "McMaster STEP files" field, select the file(s) you just
   downloaded. (Optional: also check any loose single-part studios already
   sitting in the doc from a prior "Send to Onshape" import — both get
   merged together in the same pass.)
4. Type the name you want the merged Part Studio to end up with.
5. Leave "delete originals" checked if you only want to keep the merged
   result (this is the default). It deletes both the freshly-imported
   per-file studios and any pre-existing loose studios you checked.
6. Click "Import & Merge." The log shows each step; when it says "Done,"
   reload the Onshape document tab list to see the new combined Part Studio.

## What it does under the hood

1. Uploads each selected STEP file straight into the document as its own
   new Part Studio (this is the same thing Onshape's own import dialog
   does with a single file).
2. Creates a scratch Assembly.
3. Inserts every source Part Studio's parts into it (offset along X so
   bodies don't sit exactly on top of each other -- this is cosmetic only,
   since the goal is a parts library, not a positioned physical assembly).
4. Exports that Assembly as STEP.
5. Re-imports the STEP with `flattenAssemblies=true`, which reproduces the
   Onshape import dialog's "combine into a single Part Studio" behavior --
   each solid becomes its own Part inside one new Part Studio.
6. Renames the new Part Studio to whatever you typed.
7. Deletes the scratch Assembly, and (if left checked) every source Part
   Studio -- both the ones just created from your uploads and any
   pre-existing loose ones you checked.

## One thing that's still worth watching on your first real run

`rename_element` now uses Onshape's documented Metadata API (GET the
element's metadata to find the "Name" property's id, then POST a new
value for it) instead of a guessed endpoint. This is based on real,
published Onshape docs and a forum-confirmed example, so it should work --
but if the property really isn't called "Name" on your account for some
reason, the code raises a clear error listing the actual property names it
found, rather than failing silently. If you see that error, paste it back
to me and it's a one-line fix.

## Scope note

This automates the Onshape side, including turning your locally-downloaded
McMaster STEP files into the merged Part Studio in one pass. It does not
touch McMaster's website itself -- you still click "Download" there. That's
intentional: automating McMaster's own site would mean scripting a browser
against a page that isn't built to be scripted, which breaks silently
whenever they change their layout and needs ongoing upkeep to keep working.
