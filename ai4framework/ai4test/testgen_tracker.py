import os
import time
import csv
from typing import Optional
from ai4test.ai4test_config import ai4test_dir


class TestGenTracker:
    """Light-weight, fault-tolerant tracker for focal-method test generation."""

    def __init__(self):
        self.method_info: dict[str, dict] = {}
        self.total_time: float = 0.0
        self.total_loc: int = 0

    # ───────────────────────────── LOC helpers ──────────────────────────────
    @staticmethod
    def _count_java_loc_from_string(code: str) -> int:
        if not code:
            return 0
        loc, in_block = 0, False
        for line in code.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if in_block:
                if "*/" in stripped:
                    in_block = False
                continue
            if stripped.startswith("/*"):
                in_block = True
                continue
            if stripped.startswith("//"):
                continue
            loc += 1
        return loc

    @classmethod
    def _normalize_and_count_loc(cls, code: str) -> int:
        """Always replace any escaped newlines with real newlines, then count."""
        if not code:
            return 0
        # Replace literal backslash-r backslash-n, then backslash-n
        code = code.replace("\\r\\n", "\n").replace("\\n", "\n")
        return cls._count_java_loc_from_string(code)

    @staticmethod
    def _count_java_loc_from_file(file_path: str) -> int:
        if not file_path or not os.path.isfile(file_path):
            return 0
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return TestGenTracker._count_java_loc_from_string(f.read())
        except Exception:
            return 0

    # ───────────────────────────── Core API ────────────────────────────────
    def add_method(
        self,
        method_id: str,
        *,
        file_path: str = "",
        code_string: str = ""
    ) -> None:
        if not method_id or method_id in self.method_info:
            return

        if code_string:
            loc = self._normalize_and_count_loc(code_string)
        else:
            loc = self._count_java_loc_from_file(file_path)

        self.method_info[method_id] = {
            "file": file_path or "",
            "loc": loc,
            "time": 0.0,
            "passed": False,
            "start": 0.0,
            "rounds": 0,
            "test_passed_round": 0,
            "fatal_error": False,
            "error_type": "",
        }

    def start_timer(self, method_id: str) -> None:
        if method_id in self.method_info:
            self.method_info[method_id]["start"] = time.time()

    def stop_timer(
        self,
        method_id: str,
        *,
        passed: bool = False,
        rounds: int = 1,
        passed_round: int = 0,
        fatal_error: bool = False,
        error_type: str = "",
    ) -> None:
        if method_id not in self.method_info:
            return
        entry = self.method_info[method_id]
        start = entry.get("start", 0.0)
        if not start:
            return

        elapsed = max(0.0, time.time() - start)
        entry["time"] += elapsed
        entry["passed"] = entry.get("passed", False) or passed
        entry["rounds"] = max(rounds or 0, entry.get("rounds", 0))

        # auto-fill passed_round if passed
        if entry["passed"]:
            entry["test_passed_round"] = passed_round or entry["rounds"]
        else:
            entry["test_passed_round"] = 0

        entry["fatal_error"] = fatal_error or entry.get("fatal_error", False)
        entry["error_type"] = error_type or entry.get("error_type", "")
        self.total_time += elapsed

    # ───────────────────────────── Reporting ───────────────────────────────
    def report(self, output_path: Optional[str] = None) -> None:
        if output_path is None:
            output_path = os.path.join(ai4test_dir, "testgen_report.csv")

        fieldnames = [
            "method_id",
            "class_loc",
            "total_time_sec",
            "passed",
            "rounds",
            "test_passed_round",
            "fatal_error",
            "error_type",
        ]

        try:
            with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for method_id, info in self.method_info.items():
                    writer.writerow(
                        {
                            "method_id": method_id,
                            "class_loc": info.get("loc", 0),
                            "total_time_sec": round(info.get("time", 0.0), 2),
                            "passed": info.get("passed", False),
                            "rounds": info.get("rounds", 0),
                            "test_passed_round": info.get("test_passed_round", 0),
                            "fatal_error": info.get("fatal_error", False),
                            "error_type": info.get("error_type", ""),
                        }
                    )
        except Exception as exc:
            print(f"[Tracker] Error writing CSV: {exc}")

        summary_path = os.path.join(os.path.dirname(output_path), "testgen_summary.txt")
        try:
            self.total_loc = sum(info.get("loc", 0) for info in self.method_info.values())
            with open(summary_path, "w", encoding="utf-8") as txt:
                txt.write(f"Tested {len(self.method_info)} methods\n")
                txt.write(f"Total LOC (counted per method): {self.total_loc}\n")
                txt.write(f"Total test-generation time: {round(self.total_time, 2)} seconds\n")
                txt.write(f"CSV written to: {output_path}\n")
            print(f"[Tracker] Summary written to {summary_path}")
        except Exception as exc:
            print(f"[Tracker] Error writing summary TXT: {exc}")
