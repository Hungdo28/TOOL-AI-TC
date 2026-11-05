import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "backups"


def main() -> None:
    if not BACKUP_DIR.exists():
        print("Không tìm thấy thư mục backups!")
        sys.exit(1)

    be_backup = BACKUP_DIR / "BE_backup"
    fe_backup = BACKUP_DIR / "FE_backup"
    wf_backup = BACKUP_DIR / "SUB_FLOW_memory_updated.backup.json"

    if be_backup.exists():
        shutil.copytree(be_backup, ROOT / "BE", dirs_exist_ok=True)
        print("Đã khôi phục thư mục BE từ backups/BE_backup")

    if fe_backup.exists():
        shutil.copytree(fe_backup, ROOT / "FE", dirs_exist_ok=True)
        print("Đã khôi phục thư mục FE từ backups/FE_backup")

    if wf_backup.exists():
        shutil.copy2(wf_backup, ROOT / "SUB_FLOW_memory_updated.json")
        print("Đã khôi phục SUB_FLOW_memory_updated.json")

    print("\nHoàn tất rollback code. Các file workflow n8n gốc cũng nằm sẵn tại: backups/n8n_live_backup/")


if __name__ == "__main__":
    main()
