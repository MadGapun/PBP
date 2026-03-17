export const GLOBAL_FILE_DROP_EVENT = "pbp:global-file-drop";
export const GLOBAL_FILE_DRAG_STATE_EVENT = "pbp:global-file-drag-state";

function readEntryFile(entry) {
  return new Promise((resolve) => {
    entry.file(
      (file) => resolve(file || null),
      () => resolve(null)
    );
  });
}

function readDirectoryBatch(reader) {
  return new Promise((resolve) => {
    reader.readEntries(
      (entries) => resolve(entries || []),
      () => resolve([])
    );
  });
}

async function walkDroppedEntry(entry) {
  if (!entry) return [];
  if (entry.isFile) {
    const file = await readEntryFile(entry);
    return file ? [file] : [];
  }
  if (!entry.isDirectory) return [];

  const reader = entry.createReader();
  const files = [];
  while (true) {
    const batch = await readDirectoryBatch(reader);
    if (!batch.length) break;
    for (const child of batch) {
      const nested = await walkDroppedEntry(child);
      files.push(...nested);
    }
  }
  return files;
}

export function isFileDragEvent(event) {
  const transfer = event?.dataTransfer;
  if (!transfer) return false;
  const items = Array.from(transfer.items || []);
  if (items.some((item) => item.kind === "file")) return true;
  const types = Array.from(transfer.types || []);
  return types.includes("Files");
}

export async function extractDroppedFiles(dataTransfer) {
  try {
    const items = Array.from(dataTransfer?.items || []);
    const entries = items.map((item) => item.webkitGetAsEntry?.()).filter(Boolean);
    if (!entries.length) {
      return Array.from(dataTransfer?.files || []).filter((file) => file && file.name);
    }

    const files = [];
    for (const entry of entries) {
      const nested = await walkDroppedEntry(entry);
      files.push(...nested);
    }
    return (files.length ? files : Array.from(dataTransfer?.files || [])).filter((file) => file && file.name);
  } catch {
    return Array.from(dataTransfer?.files || []).filter((file) => file && file.name);
  }
}
