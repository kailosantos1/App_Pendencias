import sqlite3
conn = sqlite3.connect("pendencias.db")
cursor = conn.cursor()
cursor.execute("DELETE FROM pendencias WHERE cliente = ?", ("studio home",))
conn.commit()
print(f"{cursor.rowcount} pendência(s) removida(s)")
conn.close()