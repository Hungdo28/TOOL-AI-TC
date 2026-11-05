import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups" / "n8n_live_backup"
DB_PATH = Path(os.environ.get("USERPROFILE", r"C:\Users\vdtchungdv")) / ".n8n" / "database.sqlite"


def slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name or "workflow").strip("_")


def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        print(f"Không tìm thấy database n8n tại: {DB_PATH}")
        return

    # Đọc ở chế độ read-only hoặc copy nhẹ để không khóa DB của n8n đang chạy
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, name, active, nodes, connections, settings, staticData, pinData, versionId, meta, updatedAt FROM workflow_entity")
    rows = cur.fetchall()
    manifest = []

    for row in rows:
        wf_id = row["id"]
        name = row["name"]
        wf_obj = {
            "name": name,
            "nodes": json.loads(row["nodes"] or "[]"),
            "pinData": json.loads(row["pinData"] or "{}") if row["pinData"] else {},
            "connections": json.loads(row["connections"] or "{}"),
            "active": bool(row["active"]),
            "settings": json.loads(row["settings"] or "{}"),
            "versionId": row["versionId"],
            "meta": json.loads(row["meta"] or "{}") if row["meta"] else {},
            "id": wf_id,
            "tags": [],
        }
        fname = f"{wf_id}_{slugify(name)}.json"
        out_path = BACKUP_DIR / fname
        out_path.write_text(json.dumps(wf_obj, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append({
            "id": wf_id,
            "name": name,
            "active": bool(row["active"]),
            "versionId": row["versionId"],
            "updatedAt": row["updatedAt"],
            "file": fname,
        })
        print(f"Backed up: {name} ({wf_id}) -> {out_path}")

    (BACKUP_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    conn.close()
    print(f"Tổng cộng đã backup {len(manifest)} workflow vào {BACKUP_DIR}")


if __name__ == "__main__":
    main()
