import sqlite3
import sys

if len(sys.argv) == 2:
    table_name = sys.argv[1]
    conn = sqlite3.connect("golf_workbench.db")
    cursor = conn.cursor()
    cursor.execute(f"DROP TABLE {table_name}")
    conn.commit()

elif len(sys.argv) < 2:
    print("No table name supplied")

else:
    print("Too many arguments")
