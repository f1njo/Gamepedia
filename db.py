import mysql.connector
import hashlib
from mysql.connector import Error


def get_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="your_pass",
        database="gamepedia"
    )
    return conn


def fetch_all_games():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM games ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def fetch_game_by_id(game_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM games WHERE id = %s", (game_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def fetch_user_by_username(username: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def create_user(username: str, password_hash: str, role: str = "user"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
        (username, password_hash, role),
    )
    conn.commit()
    cursor.close()
    conn.close()


def delete_duplicate_games_by_title() -> int:
    """
    Removes duplicated rows keeping the record with the smallest id for every title.
    Returns number of rows removed to show feedback in the UI.
    """
    conn = get_connection()
    cursor = conn.cursor()
    delete_sql = """
        DELETE g1
        FROM games g1
        INNER JOIN games g2
            ON g1.title = g2.title
            AND g1.id > g2.id
    """
    cursor.execute(delete_sql)
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return deleted
