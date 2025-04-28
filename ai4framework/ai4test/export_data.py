import os
import json
from ai4test.database import database
from tqdm import tqdm
from ai4test.ai4test_logger import logger
from ai4test.ai4test_config import dataset_dir
from multiprocessing import Pool, cpu_count
from typing import List

dataset_path = dataset_dir
db = database()


def gen_file_name(method_id, project_name, class_name, method_name, direction):
    if direction == "raw":
        return str(method_id) + "%" + project_name + "%" + class_name + "%" + method_name + "%raw.json"
    return str(method_id) + "%" + project_name + "%" + class_name + "%" + method_name + "%d" + str(
        direction) + ".json"


def create_dataset_dirs():
    def _create_folder(dir_path):
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    _create_folder(dataset_path)
    _create_folder(os.path.join(dataset_path, "direction_1"))
    _create_folder(os.path.join(dataset_path, "direction_3"))
    _create_folder(os.path.join(dataset_path, "raw_data"))


def _chunks(seq: List[int], n: int) -> List[List[int]]:
    return [seq[i : i + n] for i in range(0, len(seq), n)]


def _process_batch(id_batch: List[int]) -> None:
    from ai4test.database import database
    from ai4test.ai4test_logger import logger

    db_local = database()

    for method_id in id_batch:
        row = db_local.select(
            table_name="method",
            conditions={"id": method_id},
            result_cols=[
                "project_name", "signature", "method_name", "parameters", "source_code",
                "class_name", "dependencies", "use_field", "is_constructor",
                "is_get_set", "is_public"
            ],
        )
        if not row:
            continue

        (project_name, m_sig, method_name, parameters, source_code, class_name,
         m_deps, use_field, is_constructor, is_get_set, is_public) = row[0]

        m_deps = eval(m_deps) if isinstance(m_deps, str) else m_deps

        class_row = db_local.select(
            table_name="class",
            conditions={"project_name": project_name, "class_name": class_name},
            result_cols=[
                "class_path", "signature", "super_class", "package", "imports",
                "fields", "has_constructor", "dependencies"
            ],
        )[0]

        (class_path, c_sig, super_class, package, imports, fields,
         has_constructor, c_deps) = class_row
        c_deps = list(set(eval(c_deps))) if isinstance(c_deps, str) else c_deps

        json_data = {"focal_method": method_name, "class_name": class_name}
        direction_1 = ""
        if package:
            direction_1 += package + "\n\n"
        if imports:
            direction_1 += imports + "\n"
        direction_1 += c_sig + "{\n" + source_code + "\n"
        if fields:
            direction_1 += fields + "\n"

        methods = [x[0] for x in db_local.select(
            table_name="method",
            conditions={"class_name": class_name, "project_name": project_name},
            result_cols=["signature"]
        )]
        methods.remove(m_sig)
        direction_1 += "\n".join(methods) + "\n}"

        json_data["information"] = direction_1
        save_name = gen_file_name(method_id, project_name, class_name, method_name, 1)
        with open(os.path.join(dataset_path, "direction_1", save_name), "w") as f:
            json.dump(json_data, f)
        logger.debug(f"{save_name}, success!")

        direction_3 = {
            "c_deps": {}, "m_deps": {}, "full_fm": "",
            "focal_method": m_sig, "class_name": class_name
        }

        other_methods_list = m_deps.get("this", [])
        direction_3["full_fm"] = gen_full_context(
            project_name, class_name, method_id, other_methods_list
        )

        for dep in m_deps:
            if dep not in direction_3["m_deps"] and class_in_project(dep, project_name):
                direction_3["m_deps"][dep] = gen_required_sigs(
                    project_name, dep, m_deps[dep]
                )

        for dep in c_deps:
            if dep not in direction_3["c_deps"] and dep not in direction_3["m_deps"]:
                if class_in_project(dep, project_name):
                    direction_3["c_deps"][dep] = gen_min_sigs(project_name, dep)

        save_name = gen_file_name(method_id, project_name, class_name, method_name, 3)
        with open(os.path.join(dataset_path, "direction_3", save_name), "w") as f:
            json.dump(direction_3, f)
        logger.debug(f"{save_name}, success!")

        raw_data = {
            "id": method_id, "project_name": project_name, "signature": m_sig,
            "method_name": method_name, "parameters": parameters,
            "source_code": source_code, "class_name": class_name,
            "dependencies": m_deps, "use_field": use_field,
            "is_constructor": is_constructor, "is_get_set": is_get_set,
            "is_public": is_public, "package": package, "imports": imports
        }
        save_name = gen_file_name(method_id, project_name, class_name, method_name, "raw")
        with open(os.path.join(dataset_path, "raw_data", save_name), "w") as f:
            json.dump(raw_data, f)
        logger.debug(f"{save_name}, success!")


def export_data(batch_size: int = 200) -> None:
    create_dataset_dirs()
    total = db.select(script="SELECT COUNT(*) FROM method;")[0][0]
    id_batches = _chunks(list(range(1, total + 1)), batch_size)

    workers = min(cpu_count(), 8)
    logger.info(f"workers={workers}  batches={len(id_batches)}  batch={batch_size}")

    with Pool(processes=workers) as pool:
        for _ in tqdm(
            pool.imap_unordered(_process_batch, id_batches),
            total=len(id_batches),
            desc="Exporting batches",
            unit="batch",
            dynamic_ncols=True,
        ):
            pass

    logger.info("✅ Data Export finished.")


def gen_min_sigs(project_name: str, class_name: str) -> str:
    class_row = db.select(table_name="class",
                          conditions={"project_name": project_name, "class_name": class_name},
                          result_cols=["signature", "fields"])
    if not class_row:
        raise RuntimeError("Error happened in function gen_min_sigs.")

    c_sig, fields = class_row[0]

    full_text = c_sig + "{\n"
    full_text += fields + "\n"

    constructors = db.select(table_name="method",
                             conditions={"class_name": class_name,
                                         "is_constructor": True,
                                         "project_name": project_name},
                             result_cols=["signature"])

    for constructor in constructors:
        full_text += constructor[0] + "\n"

    full_text += "\n}"
    return full_text


def gen_required_sigs(project_name: str, class_name: str, methods_list: list):
    full_text = ""
    class_row = db.select(table_name="class",
                          conditions={"project_name": project_name, "class_name": class_name},
                          result_cols=["signature", "fields", "has_constructor"])
    if not class_row:
        raise RuntimeError("Error happened in function gen_required_sigs")

    c_sig, fields, has_constructor = class_row[0]

    full_text += c_sig + "\n" + fields + "\n"

    gs_sigs = db.select(table_name="method",
                        conditions={"project_name": project_name, "class_name": class_name,
                                    "is_get_set": True}, result_cols=["signature"])
    for gs in gs_sigs:
        full_text += gs[0] + "\n"

    constructors = db.select(table_name="method",
                             conditions={"project_name": project_name, "class_name": class_name,
                                         "is_constructor": True}, result_cols=["signature"])
    for cons in constructors:
        full_text += cons[0] + "\n"

    for parameters in methods_list:
        m_sig = db.select(table_name="method",
                          conditions={"project_name": project_name,
                                      "class_name": class_name,
                                      "parameters": parameters},
                          result_cols=["signature"])
        for sig in m_sig:
            full_text += sig[0] + "\n"

    full_text += "\n}"
    return full_text


def gen_full_context(project_name: str, class_name: str, method_id: int, dep_methods: list,
                     add_imports=True) -> str:
    class_row = db.select(table_name="class",
                          conditions={"project_name": project_name, "class_name": class_name},
                          result_cols=["class_path", "signature", "super_class", "package", "imports",
                                       "fields", "has_constructor", "dependencies"])
    if not class_row:
        raise RuntimeError("Error happened in gen_full_context.")
    class_path, c_sig, super_class, package, imports, fields, has_constructor, c_deps = class_row[0]

    fm_code = ""
    use_field = False
    row = db.select(table_name="method",
                    conditions={"project_name": project_name, "class_name": class_name,
                                "id": method_id},
                    result_cols=["use_field", "source_code"])
    if not row:
        raise RuntimeError("Error happened in gen_full_context.")
    if row[0][0]:
        use_field = True
    fm_code += row[0][1] + "\n"
    for dep in dep_methods:
        rows = db.select(table_name="method",
                         conditions={"project_name": project_name, "class_name": class_name,
                                     "parameters": dep},
                         result_cols=["use_field", "signature"])
        for row in rows:
            if row[0]:
                use_field = True
            fm_code += row[1] + "\n"

    full_text = ""
    if add_imports:
        if package:
            full_text += package + "\n" + "\n"
        full_text += imports + "\n"
    full_text += c_sig + "{\n"

    if has_constructor:
        constructors = db.select(table_name="method",
                                 conditions={"class_name": class_name,
                                             "is_constructor": True,
                                             "project_name": project_name},
                                 result_cols=["signature"])
        for constructor in constructors:
            full_text += constructor[0] + "\n"

    if use_field and fields:
        full_text += fields + "\n"
        methods = db.select(table_name="method",
                            conditions={"class_name": class_name,
                                        "is_get_set": True,
                                        "project_name": project_name},
                            result_cols=["signature"])
        for method in methods:
            full_text += method[0] + "\n"

    full_text += fm_code + "}"

    return full_text


def class_in_project(class_name: str, project_name: str):
    row = db.select(table_name="class",
                    conditions={"class_name": class_name,
                                "project_name": project_name},
                    result_cols=["class_path"])
    if row:
        return True
    return False


if __name__ == '__main__':
    export_data()