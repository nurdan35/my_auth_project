import sqlite3


def init_db():
    # Open a connection to the SQLite database
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Open and execute schema.sql file
    with open('schema.sql', 'r') as f:
        schema = f.read()
        cursor.executescript(schema)

    # Commit changes and close the connection
    conn.commit()
    conn.close()
    print("Database initialized successfully from schema.sql.")

# Run the init_db function if this script is executed directly
if __name__ == "__main__":
    init_db()
