import sqlite3

conn = sqlite3.connect("appointments.db")  # SAME database file
cursor = conn.cursor()

cursor.execute("""
ALTER TABLE appointments ADD COLUMN status TEXT DEFAULT 'Pending'
""")

conn.commit()
conn.close()

print("Status column added successfully!")