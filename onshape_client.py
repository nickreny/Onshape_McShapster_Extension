"""
Thin wrapper around the Onshape REST API for the specific merge workflow:

  1. list Part Studios in a document
  2. create a scratch Assembly
  3. insert each selected Part Studio's parts into that Assembly
  4. export the Assembly as STEP
  5. re-import that STEP, flattened, into a brand-new single Part Studio
  6. rename the result
  7. delete the scratch Assembly and the original single-part Part Studios

Auth: Onshape API keys (access key / secret key), sent as HTTP Basic auth.
Generate a key pair at https://dev-portal.onshape.com/keys -- this is a
personal, non-OAuth credential meant for exactly this kind of private script.

NOTE ON VERSION DRIFT: Onshape's API is versioned in the URL (v6, v9, v10...)
and endpoints occasionally move. Every endpoint below is based on Onshape's
published API docs / forum-confirmed examples as of this writing. Before
your first real run, sanity-check `rename_element` in particular using the
live interactive explorer at https://cad.onshape.com/glassworks/explorer --
it's the one call in this file I'd verify by hand first, since Onshape does
not publish it as prominently as the others.
"""

import io
import re
import time

import requests

BASE_URL = "https://cad.onshape.com"


class OnshapeError(RuntimeError):
    pass


class OnshapeClient:
    def __init__(self, access_key: str, secret_key: str, base_url: str = BASE_URL):
        self.auth = (access_key, secret_key)
        self.base_url = base_url.rstrip("/")

    # ---------------------------------------------------------------- utils

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs):
        resp = requests.request(method, self._url(path), auth=self.auth, timeout=60, **kwargs)
        if not resp.ok:
            raise OnshapeError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    @staticmethod
    def parse_document_url(url: str):
        """Pull (did, wvm, wvmid) out of a normal Onshape document URL."""
        match = re.search(r"/documents/([^/]+)/(w|v|m)/([^/]+)", url)
        if not match:
            raise ValueError(
                "Couldn't find a document/workspace id pair in that URL. "
                "Paste the full URL from your browser's address bar while the document is open."
            )
        return match.group(1), match.group(2), match.group(3)

    # ------------------------------------------------------------ documents

    def list_elements(self, did: str, wid: str):
        resp = self._request("GET", f"/api/v10/documents/d/{did}/w/{wid}/elements")
        return resp.json()

    def list_part_studios(self, did: str, wid: str):
        return [e for e in self.list_elements(did, wid) if e.get("type") == "Part Studio"]

    def delete_element(self, did: str, wid: str, eid: str):
        # Element deletion lives under the elements API.
        self._request("DELETE", f"/api/v10/elements/d/{did}/w/{wid}/e/{eid}")

    def rename_element(self, did: str, wid: str, eid: str, name: str):
        # VERIFY THIS ONE against the Glassworks explorer before relying on it.
        self._request(
            "POST",
            f"/api/v10/elements/d/{did}/w/{wid}/e/{eid}",
            json={"name": name},
        )

    # ------------------------------------------------------------ assembly

    def create_assembly(self, did: str, wid: str, name: str) -> str:
        resp = self._request(
            "POST",
            f"/api/v10/assemblies/d/{did}/w/{wid}",
            json={"name": name},
        )
        return resp.json()["id"]

    def insert_part_studio(
        self,
        did: str,
        wid: str,
        assembly_eid: str,
        source_did: str,
        source_eid: str,
        transform=None,
    ):
        body = {
            "documentId": source_did,
            "elementId": source_eid,
            "isAssembly": False,
            "isWholePartStudio": True,
        }
        if transform:
            body["transform"] = transform
        self._request(
            "POST",
            f"/api/v10/assemblies/d/{did}/w/{wid}/e/{assembly_eid}/instances",
            json=body,
        )

    # --------------------------------------------------------- translations

    def _poll_translation(self, request_id: str, timeout_s: int = 180):
        deadline = time.time() + timeout_s
        delay = 1.5
        while time.time() < deadline:
            resp = self._request("GET", f"/api/v10/translations/{request_id}")
            data = resp.json()
            state = data.get("requestState")
            if state == "DONE":
                return data
            if state == "FAILED":
                raise OnshapeError(f"Translation failed: {data}")
            time.sleep(delay)
            delay = min(delay * 1.4, 8)
        raise OnshapeError("Translation timed out")

    def export_assembly_step(self, did: str, wid: str, eid: str) -> bytes:
        resp = self._request(
            "POST",
            f"/api/v10/assemblies/d/{did}/w/{wid}/e/{eid}/translations",
            json={
                "formatName": "STEP",
                "storeInDocument": False,
                "allowFaultyParts": True,
            },
        )
        data = resp.json()
        result = self._poll_translation(data["id"])
        # DONE translations expose the resulting external data id(s) to download.
        ext_id = result["resultExternalDataIds"][0]
        dl = self._request("GET", f"/api/v10/documents/d/{did}/externaldata/{ext_id}")
        return dl.content

    def import_step(self, did: str, wid: str, filename: str, file_bytes: bytes) -> str:
        """Upload a STEP file into a new Part Studio.

        flattenAssemblies=True matters when this is fed the export of the
        scratch assembly (multiple bodies -> one Part Studio, one Part per
        solid). It's harmless when fed a plain single-part McMaster STEP
        file too, so this one method covers both call sites.
        """
        files = {"file": (filename, io.BytesIO(file_bytes), "application/step")}
        data = {
            "storeInDocument": "true",
            "flattenAssemblies": "true",
            "createComposite": "false",
            "allowFaultyParts": "true",
        }
        resp = self._request(
            "POST",
            f"/api/v10/translations/d/{did}/w/{wid}",
            data=data,
            files=files,
        )
        result = self._poll_translation(resp.json()["id"])
        new_eid = result["resultElementIds"][0]
        return new_eid


def grid_transform(index: int, spacing: float = 0.5) -> list:
    """A simple 4x4 transform (row-major, flattened) that offsets each
    inserted part along X so bodies don't land exactly on top of each
    other. Purely cosmetic -- doesn't matter for a parts-library Part
    Studio, just makes the intermediate assembly easier to look at.
    """
    x = index * spacing
    return [
        1, 0, 0, x,
        0, 1, 0, 0,
        0, 0, 1, 0,
        0, 0, 0, 1,
    ]
