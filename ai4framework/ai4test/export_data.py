import os
import json
from ai4test.database import database
from tqdm import tqdm
from ai4test.ai4test_logger import logger
from ai4test.ai4test_config import dataset_dir
from multiprocessing import Pool, cpu_count
from typing import Any, List

# Base dataset directory
dataset_path = dataset_dir


def gen_file_name(method_id: int, project_name: str, class_name: str, method_name: str, direction: Any) -> str:
    """Generate a standardized filename for each JSON output."""
    if direction == "raw":
        return f"{method_id}%{project_name}%{class_name}%{method_name}%raw.json"
    return f"{method_id}%{project_name}%{class_name}%{method_name}%d{direction}.json"


def create_dataset_dirs() -> None:
    """Ensure all required dataset subdirectories exist."""
    for sub in ["", "direction_1", "direction_3", "raw_data"]:
        path = os.path.join(dataset_path, sub) if sub else dataset_path
        if not os.path.exists(path):
            os.makedirs(path)


def _chunks(seq: List[int], n: int) -> List[List[int]]:
    """Split a list into smaller lists of size n."""
    return [seq[i : i + n] for i in range(0, len(seq), n)]


def _process_batch(id_batch: List[int]) -> None:
    """Worker function: fetch methods by ID, generate JSON contexts, write to files."""
    db_local = database()

    for method_id in id_batch:
        rows = db_local.select(
            table_name="method",
            conditions={"id": method_id},
            result_cols=[
                "project_name", "signature", "method_name", "parameters", "source_code",
                "class_name", "dependencies", "use_field", "is_constructor",
                "is_get_set", "is_public"
            ],
        )
        if not rows:
            continue
        project_name, m_sig, method_name, parameters, source_code, class_name, m_deps, use_field, is_constructor, is_get_set, is_public = rows[0]
        m_deps = eval(m_deps) if isinstance(m_deps, str) else m_deps

        # Direction 1: full class snippet
        class_info = db_local.select(
            table_name="class",
            conditions={"project_name": project_name, "class_name": class_name},
            result_cols=["signature", "package", "imports", "fields"],
        )[0]
        c_sig, package, imports, fields = class_info

        direction_1 = ""
        if package:
            direction_1 += package + "\n\n"
        if imports:
            direction_1 += imports + "\n"
        direction_1 += f"{c_sig}{{\n{source_code}\n"
        if fields:
            direction_1 += fields + "\n"
        all_methods = [sig[0] for sig in db_local.select(
            table_name="method",
            conditions={"project_name": project_name, "class_name": class_name},
            result_cols=["signature"]
        )]
        for sig in all_methods:
            if sig != m_sig:
                direction_1 += sig + "\n"
        direction_1 += "}"

        out1 = {"focal_method": method_name, "class_name": class_name, "information": direction_1}
        f1 = gen_file_name(method_id, project_name, class_name, method_name, 1)
        with open(os.path.join(dataset_path, "direction_1", f1), "w") as fp:
            json.dump(out1, fp)
        logger.debug(f"Wrote {f1}")

        # Direction 3: dependencies context
        direction_3 = {"c_deps": {}, "m_deps": {}, "full_fm": "", "focal_method": m_sig, "class_name": class_name}
        direction_3["full_fm"] = gen_full_context(project_name, class_name, method_id, m_deps.get("this", []))
        # method deps
        for dep, params in (m_deps or {}).items():
            if class_in_project(dep, project_name):
                direction_3["m_deps"][dep] = gen_required_sigs(project_name, dep, params)
        # class deps
        raw_cdeps = db_local.select(
            table_name="class",
            conditions={"project_name": project_name, "class_name": class_name},
            result_cols=["dependencies"]
        )[0][0]
        c_deps_list = eval(raw_cdeps) if isinstance(raw_cdeps, str) else raw_cdeps
        for dep in c_deps_list:
            if class_in_project(dep, project_name) and dep not in direction_3["m_deps"]:
                direction_3["c_deps"][dep] = gen_min_sigs(project_name, dep)

        f3 = gen_file_name(method_id, project_name, class_name, method_name, 3)
        with open(os.path.join(dataset_path, "direction_3", f3), "w") as fp:
            json.dump(direction_3, fp)
        logger.debug(f"Wrote {f3}")

        # Raw JSON dump
        raw = {"id": method_id, "project_name": project_name, "signature": m_sig, "method_name": method_name,
               "parameters": parameters, "source_code": source_code, "class_name": class_name,
               "dependencies": m_deps, "use_field": use_field, "is_constructor": is_constructor,
               "is_get_set": is_get_set, "is_public": is_public, "package": package, "imports": imports}
        froh = gen_file_name(method_id, project_name, class_name, method_name, "raw")
        with open(os.path.join(dataset_path, "raw_data", froh), "w") as fp:
            json.dump(raw, fp)
        logger.debug(f"Wrote {froh}")


def export_data(batch_size: int = 200) -> None:
    """Coordinate multiprocessing export with isolated DB connections."""
    create_dataset_dirs()
    db_main = database()
    total = db_main.select(script="SELECT COUNT(*) FROM method;")[0][0]
    batches = _chunks(list(range(1, total + 1)), batch_size)
    workers = min(cpu_count(), 8)
    logger.info(f"workers={workers}, batches={len(batches)}, batch_size={batch_size}")
    with Pool(processes=workers) as pool:
        for _ in tqdm(pool.imap_unordered(_process_batch, batches), total=len(batches), desc="Exporting batches", unit="batch", dynamic_ncols=True):
            pass
    logger.info("✅ Data export finished.")


def gen_min_sigs(project_name: str, class_name: str) -> str:
    """Generate minimal class block: signature, fields, constructors."""
    db_local = database()
    row = db_local.select(
        table_name="class",
        conditions={"project_name": project_name, "class_name": class_name},
        result_cols=["signature", "fields"]
    )
    if not row:
        raise RuntimeError("gen_min_sigs: class not found")
    c_sig, fields = row[0]
    text = f"{c_sig}{{\n{fields}\n"
    for (sig,) in db_local.select(
        table_name="method",
        conditions={"project_name": project_name, "class_name": class_name, "is_constructor": True},
        result_cols=["signature"]
    ):
        text += sig + "\n"
    text += "}\n"
    return text


def gen_required_sigs(project_name: str, class_name: str, methods_list: Any) -> str:
    """Generate dependent method signatures along with getters/setters and constructors."""
    db_local = database()
    text = ""
    row = db_local.select(
        table_name="class",
        conditions={"project_name": project_name, "class_name": class_name},
        result_cols=["signature", "fields", "has_constructor"]
    )
    if not row:
        raise RuntimeError("gen_required_sigs: class not found")
    c_sig, fields, has_constructor = row[0]
    text += f"{c_sig}\n{fields}\n"
    # getters/setters
    for (sig,) in db_local.select(
        table_name="method",
        conditions={"project_name": project_name, "class_name": class_name, "is_get_set": True},
        result_cols=["signature"]
    ):
        text += sig + "\n"
    # constructors
    if has_constructor:
        for (sig,) in db_local.select(
            table_name="method",
            conditions={"project_name": project_name, "class_name": class_name, "is_constructor": True},
            result_cols=["signature"]
        ):
            text += sig + "\n"
    # additional methods
    for params in (methods_list or []):
        for (sig,) in db_local.select(
            table_name="method",
            conditions={"project_name": project_name, "class_name": class_name, "parameters": params},
            result_cols=["signature"]
        ):
            text += sig + "\n"
    text += "}\n"
    return text


def gen_full_context(project_name: str, class_name: str, method_id: int, dep_methods: List[Any], add_imports: bool = True) -> str:
    """Assemble full class code with imports, fields, methods, and focal method."""
    db_local = database()
    row = db_local.select(
        table_name="class",
        conditions={"project_name": project_name, "class_name": class_name},
        result_cols=["signature", "package", "imports", "fields", "has_constructor", "dependencies"]
    )
    if not row:
        raise RuntimeError("gen_full_context: class not found")
    c_sig, package, imports, fields, has_constructor, raw_cdeps = row[0]
    c_deps = eval(raw_cdeps) if isinstance(raw_cdeps, str) else raw_cdeps
    # imports & class signature
    out = ""
    if add_imports:
        if package:
            out += package + "\n\n"
        out += imports + "\n"
    out += f"{c_sig}{{\n"
    # constructors
    if has_constructor:
        for (sig,) in db_local.select(
            table_name="method",
            conditions={"project_name": project_name, "class_name": class_name, "is_constructor": True},
            result_cols=["signature"]
        ):
            out += sig + "\n"
    # fields & getters/setters
    if fields:
        out += fields + "\n"
        for (sig,) in db_local.select(
            table_name="method",
            conditions={"project_name": project_name, "class_name": class_name, "is_get_set": True},
            result_cols=["signature"]
        ):
            out += sig + "\n"
    # focal method & its dependencies
    row_m = db_local.select(
        table_name="method",
        conditions={"project_name": project_name, "class_name": class_name, "id": method_id},
        result_cols=["use_field", "source_code"]
    )
    if not row_m:
        raise RuntimeError("gen_full_context: method not found")
    use_field, source = row_m[0]
    if use_field and fields:
        out += fields + "\n"
    out += source + "\n"
    for dep in (dep_methods or []):
        for (use, sig) in db_local.select(
            table_name="method",
            conditions={"project_name": project_name, "class_name": class_name, "parameters": dep},
            result_cols=["use_field", "signature"]
        ):
            if use:
                out += fields + "\n"
            out += sig + "\n"
    out += "}\n"
    return out


def class_in_project(class_name: str, project_name: str) -> bool:
    """Return True if the given class exists in the project table."""
    db_local = database()
    row = db_local.select(
        table_name="class",
        conditions={"project_name": project_name, "class_name": class_name},
        result_cols=["class_path"]
    )
    return bool(row)


if __name__ == '__main__':
    export_data()