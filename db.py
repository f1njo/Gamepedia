import mysql.connector
import hashlib
from mysql.connector import Error


def get_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="ALBLAK52",
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

def create_proposal(username: str, data: dict):
    title = (data.get("название") or "").strip()
    year_str = (data.get("год") or "").strip()
    release_year = int(year_str) if year_str.isdigit() else None
    genre = (data.get("жанр") or "").strip() or None
    developer = (data.get("разработчик") or "").strip() or None
    platforms = (data.get("платформы") or "").strip() or None
    rating_raw = (data.get("рейтинг") or "").strip()
    rating = None
    if rating_raw:
        try:
            rating_str = rating_raw.split("/")[0].strip().replace(",", ".")
            rating = float(rating_str)
        except Exception:
            rating = None

    description = (data.get("описание") or "").strip() or None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO proposals
        (username, title, release_year, genre, developer, platforms, rating, description)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (username, title, release_year, genre, developer, platforms, rating, description),
    )
    conn.commit()
    cursor.close()
    conn.close()

def delete_proposal(proposal_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM proposals WHERE id = %s", (proposal_id,))
    conn.commit()
    cursor.close()
    conn.close()

def fetch_all_proposals():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT id, username, title, release_year, genre, developer,
               platforms, rating, description, created_at
        FROM proposals
        ORDER BY created_at DESC
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def add_favorite(user_id: int, game_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT IGNORE INTO favorites (user_id, game_id) VALUES (%s, %s)",
        (user_id, game_id),
    )
    conn.commit()
    cursor.close()
    conn.close()


def remove_favorite(user_id: int, game_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM favorites WHERE user_id = %s AND game_id = %s",
        (user_id, game_id),
    )
    conn.commit()
    cursor.close()
    conn.close()


def is_favorite(user_id: int, game_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM favorites WHERE user_id = %s AND game_id = %s LIMIT 1",
        (user_id, game_id),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row is not None


def fetch_user_favorite_games(user_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT g.*
        FROM favorites f
        JOIN games g ON f.game_id = g.id
        WHERE f.user_id = %s
        ORDER BY f.created_at DESC
        """,
        (user_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
