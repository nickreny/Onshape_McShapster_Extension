import os
import traceback

from flask import Flask, jsonify, render_template, request

from onshape_client import OnshapeClient, OnshapeError

app = Flask(__name__)

ACCESS_KEY = os.environ.get("ACCESS_KEY_ONSHAPE")
SECRET_KEY = os.environ.get("SECRET_KEY_ONSHAPE")


def get_client() -> OnshapeClient:
    if not ACCESS_KEY or not SECRET_KEY:
        raise OnshapeError(
            "Set ACCESS_KEY_ONSHAPE and SECRET_KEY_ONSHAPE environment variables "
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
    delete_originals = request.form.get("deleteOriginals", "true").lower() == "true"

    existing_eids = [e for e in request.form.getlist("elementIds") if e]
    uploaded_files = request.files.getlist("files")

    log = []

    def step(msg):
        log.append(msg)

    try:
        client = get_client()

        # Build a worklist: (source_eid, output_name). Each item is
        # processed INDEPENDENTLY -- nothing gets merged across different
        # McMaster part numbers.
        work_items = []

        if uploaded_files:
            step(f"Importing {len(uploaded_files)} McMaster STEP file(s)...")
            for f in uploaded_files:
                file_bytes = f.read()
                base_name = os.path.splitext(f.filename)[0]
                new_eid = client.import_step(did, wid, f.filename, file_bytes)
                work_items.append((new_eid, base_name))
            step("Uploaded file(s) imported as individual Part Studios.")

        if existing_eids:
            # Look up current names so the result keeps the same name.
            elements = {e["id"]: e["name"] for e in client.list_elements(did, wid)}
            for eid in existing_eids:
                work_items.append((eid, elements.get(eid, "Assembled Part")))

        if not work_items:
            return jsonify({"log": log, "error": "Nothing to process -- upload file(s) and/or select existing part studios."}), 400

        results = []
        for source_eid, output_name in work_items:
            step(f"--- Assembling '{output_name}' ---")

            step("Creating assembly...")
            assembly_eid = client.create_assembly(did, wid, output_name)
            client.insert_part_studio(did, wid, assembly_eid, did, source_eid)

            step("Looking up the inserted bodies...")
            instances = client.get_assembly_instances(did, wid, assembly_eid)
            instance_ids = [inst["id"] for inst in instances]

            if len(instance_ids) > 1:
                step(f"Grouping {len(instance_ids)} bodies into one rigid unit...")
                client.add_group_feature(did, wid, assembly_eid, instance_ids)
            else:
                step("Only one body -- no grouping needed.")

            if delete_originals:
                step("Deleting the original messy multi-body Part Studio...")
                client.delete_element(did, wid, source_eid)

            results.append(assembly_eid)

        step("Done. Each item is now its own assembly with all bodies grouped into one rigid unit.")
        return jsonify({"log": log, "newElementIds": results})

    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        log.append(f"ERROR: {exc}")
        return jsonify({"log": log, "error": str(exc)}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=True, host="0.0.0.0", port=port)
