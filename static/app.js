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
  const outputName = document.getElementById("outputName").value.trim();
  const deleteOriginals = document.getElementById("deleteOriginals").checked;

  if (checked.length < 1) { log("Select at least one part studio."); return; }
  if (!outputName) { log("Enter a name for the merged part studio."); return; }

  log(`Merging ${checked.length} part studio(s) into "${outputName}"...`);
  try {
    const resp = await fetch("/api/merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        documentId: currentDoc.documentId,
        workspaceId: currentDoc.workspaceId,
        elementIds: checked,
        outputName,
        deleteOriginals,
      }),
    });
    const data = await resp.json();
    (data.log || []).forEach(log);
    if (!resp.ok) throw new Error(data.error || "Merge failed");
    log("Success. Reload the Onshape document to see the merged tab.");
  } catch (err) {
    log("ERROR: " + err.message);
  }
});
