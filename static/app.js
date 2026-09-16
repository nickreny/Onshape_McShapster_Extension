const logEl = document.getElementById("log");
function log(msg) {
  logEl.textContent += msg + "\n";
  logEl.scrollTop = logEl.scrollHeight;
}

let currentDoc = null;

document.getElementById("loadBtn").addEventListener("click", async () => {
  const docUrl = document.getElementById("docUrl").value.trim();
  if (!docUrl) return;
  log(`Loading part studios from ${docUrl} ...`);
  try {
    const resp = await fetch("/api/part-studios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_url: docUrl }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "Request failed");

    currentDoc = { documentId: data.documentId, workspaceId: data.workspaceId };
    const list = document.getElementById("studioList");
    list.innerHTML = "";
    data.partStudios.forEach((s) => {
      const row = document.createElement("label");
      row.innerHTML = `<input type="checkbox" value="${s.id}"> ${s.name}`;
      list.appendChild(row);
    });
    document.getElementById("studiosSection").hidden = false;
    log(`Found ${data.partStudios.length} part studio(s).`);
  } catch (err) {
    log("ERROR: " + err.message);
  }
});

document.getElementById("mergeBtn").addEventListener("click", async () => {
  const checked = [...document.querySelectorAll("#studioList input:checked")].map((c) => c.value);
  const files = document.getElementById("stepFiles").files;
  const deleteOriginals = document.getElementById("deleteOriginals").checked;

  if (checked.length < 1 && files.length < 1) {
    log("Upload at least one STEP file or select an existing part studio.");
    return;
  }

  log(`Assembling ${files.length} uploaded file(s) + ${checked.length} existing part studio(s)...`);

  const form = new FormData();
  form.append("documentId", currentDoc.documentId);
  form.append("workspaceId", currentDoc.workspaceId);
  form.append("deleteOriginals", deleteOriginals);
  checked.forEach((id) => form.append("elementIds", id));
  for (const f of files) form.append("files", f);

  try {
    const resp = await fetch("/api/merge", { method: "POST", body: form });
    const data = await resp.json();
    (data.log || []).forEach(log);
    if (!resp.ok) throw new Error(data.error || "Assembly failed");
    log("Success. Reload the Onshape document to see the new grouped assemblies.");
  } catch (err) {
    log("ERROR: " + err.message);
  }
});
