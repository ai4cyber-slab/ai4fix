import warnings
from typing import Union, List, Dict, Any, Optional

import mysql.connector
from mysql.connector import Error, errorcode
from ai4test.ai4test_config import config
from ai4test.ai4test_logger import logger
import os


class Database:
    def __init__(self) -> None:
        self.host: str = config.get("ai4test-database", "host")
        self.user: str = config.get("ai4test-database", "user")
        self.password: str = config.get("ai4test-database", "password")
        self.database: str = config.get("ai4test-database", "database")
        self.port: int = int(config.get("ai4test-database", "port", fallback=3306))

        self.db: Optional[mysql.connector.MySQLConnection] = None

        self._connect()

    def _connect(self) -> None:
        if self.db and self.db.is_connected():
            return

        logger.debug(f"Connecting to database at {self.host}:{self.port} as {self.user} …")
        try:
            self.db = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                autocommit=False,
            )
            logger.debug(f"Connection successful to database {self.database}")

        except Error as err:
            if err.errno == errorcode.ER_BAD_DB_ERROR:
                self.db = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    autocommit=True,
                )
                with self.db.cursor() as cur:
                    cur.execute(
                        f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                        "DEFAULT CHARACTER SET utf8mb4 "
                        "COLLATE utf8mb4_unicode_ci"
                    )
                    cur.execute(f"USE `{self.database}`")
                self.db.autocommit = False
                logger.debug(f"Connection successful to database {self.database} at {self.host}:{self.port} as {self.user} …")
            else:
                raise

    def _ensure_connection(self) -> None:
        if self.db is None or not self.db.is_connected():
            self._connect()

    def execute(self, script: str, params: Union[tuple, list] = ()) -> None:
        if not script:
            return
        self._ensure_connection()
        with self.db.cursor() as cur:
            cur.execute(script, params)
        self.db.commit()

    def execute_multi(self, script: str) -> None:
        if not script:
            return
        self._ensure_connection()
        with self.db.cursor() as cur:
            for res in cur.execute(script, multi=True):
                if res.with_rows:
                    res.fetchall()
        self.db.commit()

    def select(
        self,
        table_name: str = "",
        conditions: Optional[Dict[str, Any]] = None,
        result_cols: Union[str, List[str]] = "*",
        script: Optional[str] = None,
    ) -> List[tuple]:
        self._ensure_connection()

        with self.db.cursor() as cur:
            if script is None:
                if not table_name:
                    raise RuntimeError("If 'script' is not provided, 'table_name' is required.")

                columns = (
                    ", ".join(result_cols) if isinstance(result_cols, list) else result_cols
                )
                sql = f"SELECT {columns} FROM {table_name}"

                params: List[Any] = []
                if conditions:
                    where_parts = []
                    for k, v in conditions.items():
                        if v is None:
                            where_parts.append(f"{k} IS %s")
                        else:
                            where_parts.append(f"{k} = %s")
                        params.append(v)
                    sql += " WHERE " + " AND ".join(where_parts)

                cur.execute(sql, params)
            else:
                cur.execute(script)

            return cur.fetchall()

    def insert(self, table_name: str, row: Dict[str, Any]) -> None:
        placeholders = ", ".join(["%s"] * len(row))
        columns = ", ".join(row.keys())
        values = tuple(row.values())
        sql = f"INSERT IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})"

        try:
            self.execute(sql, values)
        except Error as e:
            warnings.warn(f"Insert failed: {e}\nSQL: {sql}")

    def update(
        self,
        table_name: str,
        conditions: Dict[str, Any],
        new_cols: Dict[str, Any],
    ) -> None:
        set_clause = ", ".join([f"{k} = %s" for k in new_cols])
        where_clause = " AND ".join([f"{k} = %s" for k in conditions])
        sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
        params = list(new_cols.values()) + list(conditions.values())
        self.execute(sql, params)


database = Database


def create_table() -> None:
    db = Database()
    db.execute_multi(
        """
        CREATE TABLE IF NOT EXISTS `class` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `project_name` VARCHAR(255) NOT NULL,
            `class_name` VARCHAR(255) NOT NULL,
            `class_path` VARCHAR(255) NOT NULL,
            `signature` TEXT NOT NULL,
            `super_class` TEXT NULL,
            `package` TEXT NULL,
            `imports` TEXT NULL,
            `fields` LONGTEXT NULL,
            `has_constructor` TINYINT(1) NOT NULL,
            `dependencies` TEXT NULL,
            CONSTRAINT UNIQUE `u_class_project_name` (`project_name`, `class_name`)
        );

        CREATE TABLE IF NOT EXISTS `method` (
            `id` INT AUTO_INCREMENT PRIMARY KEY,
            `project_name` VARCHAR(255) NOT NULL,
            `signature` TEXT NOT NULL,
            `method_name` VARCHAR(255) NOT NULL,
            `parameters` TEXT NOT NULL,
            `source_code` LONGTEXT NOT NULL,
            `class_name` VARCHAR(255) NOT NULL,
            `dependencies` LONGTEXT NULL,
            `use_field` TINYINT(1) NOT NULL,
            `is_constructor` TINYINT(1) NOT NULL,
            `is_get_set` TINYINT(1) NOT NULL,
            `is_public` TINYINT(1) NOT NULL
        );
    """
    )


def drop_table() -> None:
    db = Database()
    db.execute_multi("DROP TABLE IF EXISTS `method`; DROP TABLE IF EXISTS `class`;")

def get_java_file_paths(class_name):
    db = Database()
    db._ensure_connection()
    with db.db.cursor() as cur:
        query = "SELECT `class_path` FROM `class` WHERE `class_name` = %s;"
        cur.execute(query, (class_name,))
        results = cur.fetchall()
    return [os.path.abspath(row[0]) for row in results]