# Onshape McMaster Assembler (RM internal tool)

Some McMaster-Carr STEP files come in as a messy multi-body Part Studio --
one tab, but several loose separate bodies representing the item's
sub-components (a fitting's nut, ferrule, body, etc., all in one file).
That's normally a pain: using it in a downstream assembly means manually
mating every one of those bodies together, every time.

This tool automates the fix: for each McMaster part, it builds a small
assembly containing that part, and adds a **Group** feature locking all
its bodies at their current relative positions as one rigid unit -- the
same feature you'd get by manually selecting everything and choosing
Group in Onshape. From then on, that assembly behaves as one solid item
you can drop into other assemblies with a single mate, no re-mating its
internal pieces ever again.

It processes each McMaster part independently -- nothing gets merged
together across different part numbers.

## Running it via GitHub Codespaces (no local install needed)

If you don't want to install Python locally, push this folder to a GitHub
repo and run it in a Codespace instead — everything happens in the browser.

1. Create a new repo on GitHub (private is fine) and push this folder to it.
2. On the repo page: **Code** → **Codespaces** tab → **Create codespace on main**.
   Wait ~1 minute — it builds a container and runs `pip install -r requirements.txt`
   automatically (see `.devcontainer/devcontainer.json`).
3. Add your API key as secrets so you don't have to paste it every session:
   GitHub → your avatar → **Settings** → **Codespaces** → **Secrets** →
   **New secret**. Add `ACCESS_KEY_ONSHAPE` and `SECRET_KEY_ONSHAPE`, and
   allow them for this repository. Then **fully stop and restart** the
   Codespace so it picks them up -- secrets only load at container startup.
4. In the Codespace's terminal (Terminal → New Terminal if it's not open), run:
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
   Sign in to cad.onshape.com, click your avatar → **My account** →
   **Developer** (the old dev-portal.onshape.com is being retired --
   use this location). Create a new API key with read/write access.
   You'll get an access key and a secret key — the secret is shown once,
   save it somewhere safe (a password manager, not this repo).

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
   downloaded. (Optional: also check any already-imported messy multi-body
   studios sitting in the doc -- each gets processed independently, same
   as the freshly uploaded ones.)
4. Leave "delete originals" checked if you only want to keep the final
   assembly for each item (this is the default).
5. Click "Assemble & Group." The log shows each step per item; when it
   says "Done," reload the Onshape document to see the results.
6. In Onshape, drag the new assembly tabs into whatever folder you want to
   organize them under (e.g. "CAD Imports") -- Onshape doesn't expose
   tab-folder creation/assignment to the API, so this one step stays manual.

## What it does under the hood

For each uploaded file or selected existing Part Studio, independently:

1. Imports (or uses the existing) Part Studio as-is -- this is often the
   messy multi-body tab McMaster's file produces.
2. Creates a new assembly (named after the part) and inserts that Part
   Studio's parts into it.
3. Looks up the resulting occurrence IDs and adds a **Group** feature
   covering all of them, locking them at their current relative positions
   as one rigid unit. This uses the real feature JSON Onshape generates
   for a manual Group (confirmed by reading back an assembly where this
   was done by hand), not a guess from documentation.
4. Deletes the original messy Part Studio, if "delete originals" is checked.

## What's deliberately left manual

Two things Onshape doesn't expose to the API, so they stay manual by design
rather than relying on fragile scraping or undocumented endpoints:

- **Fastening the result to the assembly origin.** Onshape's Fasten mate
  references specific mate-connector IDs that are unique per-assembly and
  don't transfer to a script running on fresh parts. Group alone already
  solves the actual problem (no more re-mating internal pieces every time)
  -- you'll add one mate to position the finished assembly wherever it's
  going, same as you would for any single purchased part.
- **Organizing tabs into an Onshape folder.** Real Onshape feature, but
  UI-only -- no API for creating one or moving tabs into it.

## One thing that's still worth watching on your first real run

`rename_element` uses Onshape's documented Metadata API (GET the
element's metadata to find the "Name" property's id, then POST a new
value for it) instead of a guessed endpoint. This is based on real,
published Onshape docs and a forum-confirmed example, so it should work --
but if the property really isn't called "Name" on your account for some
reason, the code raises a clear error listing the actual property names it
found, rather than failing silently. If you see that error, paste it back
and it's a one-line fix.

## Scope note

This automates the Onshape side: turning locally-downloaded McMaster STEP
files (or already-imported messy ones) into one grouped assembly each.
It does not touch McMaster's website itself -- you still click "Download"
there.
