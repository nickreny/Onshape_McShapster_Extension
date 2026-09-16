import os
import traceback

from flask import Flask, jsonify, render_template, request

from onshape_client import OnshapeClient, OnshapeError, grid_transform

app = Flask(__name__)

ACCESS_KEY = os.environ.get("ONSHAPE_ACCESS_KEY")
SECRET_KEY = os.environ.get("ONSHAPE_SECRET_KEY")


def get_client() -> OnshapeClient:
    if not ACCESS_KEY or not SECRET_KEY:
        raise OnshapeError(
            "Set ONSHAPE_ACCESS_KEY and ONSHAPE_SECRET_KEY environment variables "
            "before starting the app (see README)."
        )
    return OnshapeClient(ACCESS_KEY, SECRET_KEY)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/part-studios", methods=["POST"])
def api_part_studios():
    try:
        client = get_client()
        did, wvm, wvmid = client.parse_document_url(request.json["doc_url"])
        if wvm != "w":
            return jsonify({"error": "That URL points at a version/microversion, not a workspace. "
                                      "Open the document normally (not a fixed version) and copy that URL."}), 400
        studios = client.list_part_studios(did, wvmid)
        return jsonify({
            "documentId": did,
            "workspaceId": wvmid,
            "partStudios": [{"id": s["id"], "name": s["name"]} for s in studios],
        })
    except Exception as exc:  # noqa: BLE001 -- surfaced to the UI log, not swallowed
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 400


@app.route("/api/merge", methods=["POST"])
def api_merge():
    # multipart/form-data: regular fields come through request.form,
    # uploaded files through request.files.
    did = request.form["documentId"]
    wid = request.form["workspaceId"]
    output_name = request.form["outputName"].strip()
    delete_originals = request.form.get("deleteOriginals", "true").lower() == "true"

    # elementIds of studios the user checked that already existed in the doc
    existing_eids = [e for e in request.form.getlist("elementIds") if e]
    uploaded_files = request.files.getlist("files")

    log = []

    def step(msg):
        log.append(msg)

    try:
        client = get_client()
        source_eids = list(existing_eids)

        if uploaded_files:
            step(f"Importing {len(uploaded_files)} McMaster STEP file(s)...")
            for f in uploaded_files:
                file_bytes = f.read()
                new_eid = client.import_step(did, wid, f.filename, file_bytes)
                source_eids.append(new_eid)
            step("All uploaded files are now individual Part Studios.")

        if len(source_eids) < 1:
            return jsonify({"log": log, "error": "Nothing to merge -- upload file(s) and/or select existing part studios."}), 400

        step(f"Creating scratch assembly for {len(source_eids)} part studio(s)...")
        assembly_eid = client.create_assembly(did, wid, "_merge_scratch")

        for i, eid in enumerate(source_eids):
            client.insert_part_studio(did, wid, assembly_eid, did, eid, transform=grid_transform(i))
        step("Inserted all selected part studios into the scratch assembly.")

        step("Exporting scratch assembly as STEP...")
        step_bytes = client.export_assembly_step(did, wid, assembly_eid)

        step("Re-importing STEP, flattened, into a new combined Part Studio...")
        new_eid = client.import_step(did, wid, f"{output_name}.step", step_bytes)

        step(f"Renaming combined Part Studio to '{output_name}'...")
        client.rename_element(did, wid, new_eid, output_name)

        step("Cleaning up scratch assembly...")
        client.delete_element(did, wid, assembly_eid)

        if delete_originals:
            step("Deleting original single-part Part Studios (including freshly imported ones)...")
            for eid in source_eids:
                client.delete_element(did, wid, eid)

        step("Done.")
        return jsonify({"log": log, "newElementId": new_eid})

    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        log.append(f"ERROR: {exc}")
        return jsonify({"log": log, "error": str(exc)}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=True, host="0.0.0.0", port=port)
