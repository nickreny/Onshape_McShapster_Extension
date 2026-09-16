"""
Thin wrapper around the Onshape REST API for turning messy multi-body
McMaster STEP imports into usable rigid assemblies, one item at a time:

  1. import the STEP file -- lands as one Part Studio with several loose
     bodies (McMaster's file itself, not a code issue)
  2. create an assembly and insert that Part Studio's parts into it
  3. add a Group feature covering every inserted occurrence, locking them
     at their current relative positions as one rigid unit (this is the
     same feature Onshape creates for a manual Group -- built from the
     real JSON Onshape generated for one, not guessed from docs)
  4. rename the assembly to the part name
  5. delete the original messy Part Studio

Auth: Onshape API keys (access key / secret key), sent as HTTP Basic auth.
Generate a key pair at https://dev-portal.onshape.com/keys -- this is a
personal, non-OAuth credential meant for exactly this kind of private script.

NOTE ON VERSION DRIFT: Onshape's API is versioned in the URL (v6, v9, v10...)
and endpoints occasionally move. Every endpoint below is based on Onshape's
published API docs / forum-confirmed examples as of this writing.
rename_element uses the documented Metadata API (a GET to find the "Name"
property's id, then a POST to set it) rather than a guessed endpoint -- if
the property lookup ever fails, it raises a clear error listing the actual
property names found, instead of failing silently.
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
        """Rename an element via Onshape's Metadata API. Not currently
        called by app.py (create_assembly already names the assembly at
        creation time), but kept here since it's independently useful.

        This is a two-step dance: fetch the element's current metadata to
        find the Name property's id and href, then POST a new value for
        just that property. There's no simpler one-shot rename endpoint.
        """
        meta = self._request("GET", f"/api/v10/metadata/d/{did}/w/{wid}/e/{eid}").json()
        name_prop = next(
            (p for p in meta["properties"] if str(p.get("name", "")).lower() == "name"),
            None,
        )
        if name_prop is None:
            available = [p.get("name") for p in meta["properties"]]
            raise OnshapeError(
                f"Couldn't find a 'Name' property to rename via the metadata API. "
                f"Available property names on this element: {available}. "
                f"Check https://cad.onshape.com/glassworks/explorer for the right one."
            )
        self._request(
            "POST",
            f"/api/v10/metadata/d/{did}/w/{wid}/e/{eid}",
            json={
                "items": [{
                    "href": meta["href"],
                    "properties": [{"propertyId": name_prop["propertyId"], "value": name}],
                }]
            },
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

    def get_assembly_instances(self, did: str, wid: str, eid: str) -> list:
        """Return the top-level instances (occurrences) currently in an
        assembly -- each dict includes an "id" usable as a Group feature's
        occurrence path.
        """
        resp = self._request("GET", f"/api/v10/assemblies/d/{did}/w/{wid}/e/{eid}")
        return resp.json().get("rootAssembly", {}).get("instances", [])

    def add_group_feature(self, did: str, wid: str, assembly_eid: str, instance_ids: list, name: str = "Group 1"):
        """Add a Group feature locking the given occurrences at their
        current relative positions -- the same feature Onshape creates
        when you manually select bodies and choose Group. Built from the
        real JSON Onshape generated for a manual Group (BTMMateGroup-65 /
        BTMIndividualOccurrenceQuery-626), not guessed from docs.
        """
        queries = [
            {"btType": "BTMIndividualOccurrenceQuery-626", "path": [instance_id]}
            for instance_id in instance_ids
        ]
        feature = {
            "btType": "BTMMateGroup-65",
            "featureType": "mateGroup",
            "name": name,
            "suppressed": False,
            "parameters": [{
                "btType": "BTMParameterQueryWithOccurrenceList-67",
                "queries": queries,
                "parameterId": "occurrencesQuery",
            }],
        }
        self._request(
            "POST",
            f"/api/v10/assemblies/d/{did}/w/{wid}/e/{assembly_eid}/features",
            json={"feature": feature},
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

    def import_step(self, did: str, wid: str, filename: str, file_bytes: bytes) -> str:
        """Upload a STEP file into a new Part Studio (plain import -- a
        multi-body McMaster file lands as one Part Studio with several
        loose Parts, which is expected; the Group feature is what makes
        it usable as one rigid unit afterward).
        """
        files = {"file": (filename, io.BytesIO(file_bytes), "application/step")}
        data = {
            "storeInDocument": "true",
            "flattenAssemblies": "true",
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
