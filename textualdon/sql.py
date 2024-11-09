# Standard library imports
from __future__ import annotations
from typing import Sequence, Any
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from importlib import resources

# Textual imports
from textual.dom import DOMNode


class SQLite(DOMNode):
    """A simple SQLite database wrapper for TextualDon.   
    Cannot attach child widgets (blocked)."""


    def __init__(
            self,
            app_name: str,
            data_dir: Path,
            sql_script: str,
            db_filename: str = None,
            del_on_start: bool = False,
            **kwargs):
        """Create a new SQLite database wrapper.    
        Must pass in `app_name`: the name of the package that is using this widget.   
        This same name will be used to create a directory in the user's data directory to store the database file.

        `del_on_start` will delete the existing database file and create a new one (for dev mode).

        Args:
            app_name: This must be the name of the package that is using this widget.
                This MUST be the same name as your program / main package.
            data_dir: Directory on user's computer where the folder will be created.
            sql_script: The name of the SQL script file to use for setting up the database tables and schema.   
                Path is relative to the main package directory.
            db_filename: The name the database file will use. If None, name will be `<app_name>.db`.
            del_on_start: Whether to delete the database file on start. Defaults to False.
            name: The name of the widget.
            id: The ID of the widget in the DOM.
            classes: The CSS classes for the widget.

        EXAMPLE:
        ```
        db = SQLite("my_package", "create_tables.sql")
        ```
        
        """

        super().__init__(**kwargs)

        self.log(
            "SQLite widget initialized. \n"
            f"SQLite Version: {sqlite3.sqlite_version}\n"
            f"Library Version: {sqlite3.version}\n"
        )

        self.app_name:    str = app_name
        self.data_dir:   Path = data_dir
        self.sql_script:  str = sql_script
        self.db_filename: str = db_filename or f"{app_name}.db"
        self.del_on_start:  bool = del_on_start
        self.readonly_mode: bool = False

        self.user_db_path = self.data_dir / self.db_filename
        
        if self.user_db_path.exists() and self.del_on_start:
            print(f"del_on_start: {del_on_start}  |  DELETING existing database file!")
            self.user_db_path.unlink()   

        exists = self.user_db_path.exists()

        self.connection = sqlite3.connect(self.user_db_path)    
        if not exists:
            try:
                self.initialize_db()
            except Exception as e:
                e.add_note("Error initializing database.")
                raise e
    
    def initialize_db(self):

        # here it looks up the file in the package directory.
        # This is why we must pass in the app_name, so it knows what package to look for.

        sql_file_path = Path(resources.files(self.app_name) / self.sql_script)
        print(f"SQL file location: \n{sql_file_path} \n")
        with open(sql_file_path, 'r') as f:
            script = f.read()
            self.execute_script(script)

    @contextmanager
    def _cursor(self):
        """Used internally by class"""

        cursor = self.connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    def execute_script(self, script: str): 
        """Execute a SQL script on the database.

        EXAMPLE:
        ```
        script = "create_table.sql"
        db.execute_script(script)
        ``` """

        with self.app.capture_exceptions():
            with self._cursor() as cursor:
                cursor.executescript(script)
            self.connection.commit()
            if self.app.error:
                self.connection.rollback()
                print("ERROR executing script on database.")
            else:
                print("Successfully executed script on database.")


    def insert_one(self, table: str, columns: list[str], values: Sequence[Any], auto_commit: bool = True):
        """Insert a single row into the database.   
        Using the auto_commit parameter, you can stage multiple inserts before committing them all at once.
        Simply let it go back to the default value of True to commit all inserts.

        EXAMPLE:
        ```    
        table = "users"
        columns = ["name", "age", "email"]
        values = ["Alice", 30, "alice@example.com"]
        db.insert_one(table, columns, values)
        ```
        Raw SQL:   
        `INSERT INTO {table} ({', '.join(columns)}) VALUES (?, ?, ?);`

        Args:
            table (str): The name of the table to insert the row into.
            columns (list[str]): The list of column names.
            values (Sequence[Any]): List or tuple of values to insert.
            auto_commit (bool, optional): Whether to commit the transaction automatically. Defaults to True.
        """

        if self.readonly_mode:
            self.app.notify("Database is in read-only mode. Can't save changes.")
            return

        placeholders = ', '.join(['?'] * len(values))
        query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"

        with self.app.capture_exceptions():
            with self._cursor() as cursor:
                cursor.execute(query, values)   
            if auto_commit:
                self.connection.commit()
            if self.app.error:
                self.connection.rollback()

        self.log.debug(f"Successfully inserted a row into {table} with values {values}.")


    def delete_one(self, table_name: str, column_name: str, value: Any):
        """Delete a row from a database table.

        EXAMPLE:
        ```
        db.delete_one('employees', 'id', 3)
        ```
        Raw SQL:   
        `DELETE FROM {table_name} WHERE {column_name} = ?;` """

        if self.readonly_mode:
            self.app.notify("Database is in read-only mode. Can't save changes.")
            return
        
        sql_delete_query = f"DELETE FROM {table_name} WHERE {column_name} = ?;"

        with self.app.capture_exceptions():
            with self._cursor() as cursor:
                cursor.execute(sql_delete_query, (value,))
            self.connection.commit()
            if self.app.error:
                self.connection.rollback()

        self.log.debug(f"Successfully deleted {table_name} row where {column_name} is {value}.")

    def update_column(
            self,
            table_name: str,
            column_name: str,
            new_value: Any,
            condition_column: str,
            condition_value: Any
        ):
        """Update a column in a database table.
        
        EXAMPLE:
        ```
        db.update_column('employees', 'salary', 75000, 'id', 3)
        ``` 
        Raw SQL:   
        `UPDATE {table_name} SET {column_name} = ? WHERE {condition_column} = ?; `"""

        if self.readonly_mode:
            self.app.notify("Database is in read-only mode. Can't save changes.")
            return
        
        sql_update_query = f"UPDATE {table_name} SET {column_name} = ? WHERE {condition_column} = ?;"

        with self.app.capture_exceptions():
            with self._cursor() as cursor:
                cursor.execute(sql_update_query, (new_value, condition_value))
            self.connection.commit()
            if self.app.error:
                self.connection.rollback()

        self.log.debug(
            f"Successfully updated {table_name} column {column_name} to "
            f"{new_value} where {condition_column} is {condition_value}."
        )

    def fetchall(self, query: str, params: Sequence = None) -> list[tuple]:
        """This method runs a SQL query and retrieves all rows that match the query criteria.
        
        EXAMPLE:
        ```
        query = "SELECT * FROM users WHERE name = ?"
        params = ("Alice",)   # Note the comma, (must be sequence)
        rows = db.fetchall(query, params)
        ``` 
        Or use the shortcut:
        ```
        row = db.fetchone("SELECT * FROM users WHERE name = ?", ("Alice",))
        ```
        Args:
            query (str): The SQL query to run.
            params (Sequence, optional): The query parameters. Defaults to None.

        Returns:
            list[tuple]: A list of rows that match the query criteria.
        """

        with self.app.capture_exceptions():
            with self._cursor() as cursor:
                cursor.execute(query, params or [])
                return cursor.fetchall()
            if self.app.error:
                self.connection.rollback()     

    
    def fetchone(self, query: str, params: Sequence = None) -> tuple:
        """This method is similar to fetchall, but it only retrieves a single row
        from the database, even if multiple rows meet the query criteria.
        
        EXAMPLE:
        ```
        query = "SELECT * FROM users WHERE name = ?"
        params = ("Alice",)   # Note the comma, (must be sequence)
        row = db.fetchone(query, params)
        ``` 
        Or use the shortcut:
        ```
        row = db.fetchone("SELECT * FROM users WHERE name = ?", ("Alice",))
        ```

        Args:
            query (str): The SQL query to run.
            params (Sequence, optional): The query parameters. Defaults to None.

        Returns:
            tuple: A single row that matches the query criteria.
        """
        with self.app.capture_exceptions():
            with self._cursor() as cursor:
                cursor.execute(query, params or [])
                return cursor.fetchone()
            if self.app.error:
                    self.connection.rollback()
    
    def close(self):
        """Close the database connection."""
        self.connection.close()






