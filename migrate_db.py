"""
Database migratiescript voor Menu Maker.

Veilig meerdere keren te draaien (idempotent).
Gebruik: python migrate_db.py

Migraties:
  - Maakt tabel `ingredient_voorstellen` aan als die nog niet bestaat.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "menu_maker.db"


def run_migrations():
    if not DB_PATH.exists():
        print(f"Database niet gevonden op {DB_PATH}")
        print("Start eerst de app zodat db.create_all() de initiële tabellen aanmaakt.")
        return

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # --- Migratie: ingredient_voorstellen tabel ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredient_voorstellen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organisatie_id INTEGER NOT NULL REFERENCES organisaties(id),
            menu_id INTEGER NOT NULL REFERENCES menus(id),
            data JSON NOT NULL,
            status VARCHAR(20) DEFAULT 'nieuw',
            aangemaakt_op DATETIME
        )
    """)
    print("  ingredient_voorstellen: OK (aangemaakt of al aanwezig)")

    con.commit()
    con.close()
    print("\nMigratie voltooid.")


if __name__ == "__main__":
    print(f"Database: {DB_PATH}")
    print("Migraties uitvoeren...\n")
    run_migrations()
