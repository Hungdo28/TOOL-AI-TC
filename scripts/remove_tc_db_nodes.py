import json

def remove_tc_db_nodes(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        wf = json.load(f)

    # 1. Remove nodes
    wf["nodes"] = [n for n in wf.get("nodes", []) if n.get("name") not in ("Mem_TC_Build", "Mem_TC_Insert")]

    # 2. Clean connections
    conn = wf.get("connections", {})
    conn.pop("Mem_TC_Build", None)
    conn.pop("Mem_TC_Insert", None)

    for src, outputs in conn.items():
        for c_type, c_lists in outputs.items():
            for i, c_list in enumerate(c_lists):
                c_lists[i] = [dest for dest in c_list if dest.get("node") not in ("Mem_TC_Build", "Mem_TC_Insert")]

    with open(file_path, "w", encoding="utf-8", newline="") as f:
        json.dump(wf, f, ensure_ascii=False, indent=2)
    print(f"Successfully updated {file_path}")

remove_tc_db_nodes("SUB_FLOW_memory_updated.json")
remove_tc_db_nodes("SUB_FLOW_memory_optimized.json")
