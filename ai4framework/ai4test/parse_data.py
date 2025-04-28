from __future__ import annotations
import os
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any, Dict, List, Set

from tqdm import tqdm

try:
    import orjson as _json
    _loads = _json.loads
except ModuleNotFoundError:
    import json as _json
    _loads = _json.loads

from ai4test.database import database
from ai4test.ai4test_logger import logger

def _gather_json_files(dir_path: str | os.PathLike[str]) -> List[str]:
    return [
        os.path.join(root, f)
        for root, _, files in os.walk(dir_path)
        for f in files if f.endswith(".json")
    ]


def _insert_ignore_dupe(db: database, table: str, row: Dict[str, Any]) -> None:
    try:
        db.insert(table, row=row)
    except Exception as exc:
        if "Duplicate entry" not in str(exc) and "1062" not in str(exc):
            raise


_global_db: database | None = None


def _init_worker() -> None:
    global _global_db
    _global_db = database()


def _process_batch(batch: List[str]) -> None:
    assert _global_db is not None
    db = _global_db
    seen: Set[str] = set()

    with db.db:
        for fp in batch:
            with open(fp, "r", encoding="utf-8") as f:
                data = _loads(f.read())

            for cls in data:
                proj = cls["project_name"]
                cname = cls["class_name"]
                key = f"{proj}::{cname}"

                class_row = {
                    "project_name": proj,
                    "class_name": cname,
                    "class_path": cls["class_path"],
                    "signature": cls["c_sig"],
                    "super_class": (cls["superclass"].split(" ")[1]
                                    if cls["superclass"] else ""),
                    "package": cls.get("package", ""),
                    "imports": "\n".join(cls["imports"]) if cls["imports"] else "",
                    "fields": "\n".join({f["original_string"] for f in cls["fields"]}),
                    "has_constructor": cls["has_constructor"],
                    "dependencies": "{}",
                }

                ctor_deps: Dict[str, List[str]] = {}
                for m in cls["methods"]:
                    method_row = {
                        "project_name": proj,
                        "signature":   m["m_sig"],
                        "method_name": m["method_name"],
                        "parameters":  m["parameters"],
                        "source_code": m["source_code"],
                        "class_name":  cname,
                        "dependencies": str(m["m_deps"]),
                        "use_field":   m["use_field"],
                        "is_constructor": m["is_constructor"],
                        "is_get_set":  m["is_get_set"],
                        "is_public":   "public" in m["modifiers"],
                    }
                    _insert_ignore_dupe(db, "method", method_row)

                    if m["is_constructor"]:
                        for dep_cls, params in m["m_deps"].items():
                            ctor_deps.setdefault(dep_cls, []).extend(params)

                class_row["dependencies"] = str(ctor_deps)
                if key not in seen:
                    _insert_ignore_dupe(db, "class", class_row)
                    seen.add(key)


def _chunks(seq: List[str], size: int) -> List[List[str]]:
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def parse_data(dir_path: str | os.PathLike[str], *, batch_size: int = 15) -> None:
    files = _gather_json_files(str(dir_path))
    if not files:
        logger.warning("No JSON files found – nothing to parse.")
        return

    batches = _chunks(files, batch_size)
    workers = min(cpu_count(), 8)

    logger.info(f"workers={workers} batches={len(batches)} batch_size={batch_size}")

    with Pool(processes=workers, initializer=_init_worker) as pool:
        for _ in tqdm(pool.imap_unordered(_process_batch, batches),
                      total=len(batches),
                      desc="JSON batches",
                      unit="batch",
                      dynamic_ncols=True,
                      smoothing=0.1):
            pass

    logger.info("✅ JSON import finished.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_data.py <folder_with_json>")
        sys.exit(1)

    parse_data(Path(sys.argv[1]))
