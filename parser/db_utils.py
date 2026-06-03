# parser/db_utils.py
import psycopg2
from urllib.parse import urlparse
from config import DATABASE_DSN

def get_db_connection():
    """Создаёт подключение к PostgreSQL"""
    parsed = urlparse(DATABASE_DSN)
    
    conn = psycopg2.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname or 'localhost',
        port=parsed.port or 5432,
        database=parsed.path[1:] if parsed.path else 'livebook_corpus'
    )
    return conn

def get_chapter_id(conn, chapter_name='Выпуск 1962'):
    """Возвращает ID раздела"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chapters WHERE name = %s", (chapter_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO chapters (name) VALUES (%s) RETURNING id", (chapter_name,))
    conn.commit()
    return cursor.fetchone()[0]


def get_or_create_folder(conn, folder_name, parent_path, parent_db_id=None, chapter_id=None):
    """
    Создаёт или возвращает папку с привязкой к разделу.

    Параметры:
    - folder_name: имя папки
    - parent_path: полный путь (для full_path)
    - parent_db_id: ID родительской папки (может быть None)
    - chapter_id: ID раздела (обязателен для корневых папок, для дочерних может быть None)
    """
    cursor = conn.cursor()

    # Строим запрос в зависимости от наличия родителя и раздела
    if parent_db_id:
        # Дочерняя папка — наследуем chapter_id от родителя или берём переданный
        if chapter_id is None:
            # Получаем chapter_id от родительской папки
            cursor.execute("SELECT chapter_id FROM folders WHERE id = %s", (parent_db_id,))
            row = cursor.fetchone()
            chapter_id = row[0] if row else None

        cursor.execute(
            """
            SELECT id FROM folders 
            WHERE name = %s AND parent_folder_id = %s
            """,
            (folder_name, parent_db_id)
        )
    else:
        # Корневая папка — обязательно нужен chapter_id
        cursor.execute(
            """
            SELECT id FROM folders 
            WHERE name = %s AND parent_folder_id IS NULL AND chapter_id = %s
            """,
            (folder_name, chapter_id)
        )

    row = cursor.fetchone()
    if row:
        return row[0]

    # Создаём новую папку
    full_path = f"{parent_path}/{folder_name}" if parent_path else folder_name
    cursor.execute(
        """
        INSERT INTO folders (name, parent_folder_id, full_path, chapter_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (folder_name, parent_db_id, full_path, chapter_id)
    )
    conn.commit()
    return cursor.fetchone()[0]

def get_or_create_chapter_by_name(conn, chapter_name):
    """Возвращает ID раздела по имени, создаёт если нет"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chapters WHERE name = %s", (chapter_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO chapters (name) VALUES (%s) RETURNING id", (chapter_name,))
    conn.commit()
    return cursor.fetchone()[0]


def save_document(conn, title, file_type, folder_id, content, url, creation_date, chapter_id=None):
    """Сохраняет документ"""
    cursor = conn.cursor()

    # Если chapter_id не передан, пытаемся получить из папки
    if chapter_id is None and folder_id is not None:
        cursor.execute("SELECT chapter_id FROM folders WHERE id = %s", (folder_id,))
        row = cursor.fetchone()
        chapter_id = row[0] if row else get_chapter_id(conn)
    elif chapter_id is None:
        chapter_id = get_chapter_id(conn)

    cursor.execute(
        """
        INSERT INTO documents (title, type, chapter_id, folder_id, content, url, creation_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (title, file_type, chapter_id, folder_id, content, url, creation_date)
    )
    conn.commit()
    return cursor.fetchone()[0]


def save_media(conn, folder_id, document_id, name, media_bytes, chapter_id=None):
    """Сохраняет медиафайл (изображение)"""
    cursor = conn.cursor()

    # Если chapter_id не передан, пытаемся получить из папки или документа
    if chapter_id is None:
        if folder_id is not None:
            cursor.execute("SELECT chapter_id FROM folders WHERE id = %s", (folder_id,))
            row = cursor.fetchone()
            chapter_id = row[0] if row else None
        if chapter_id is None and document_id is not None:
            cursor.execute("SELECT chapter_id FROM documents WHERE id = %s", (document_id,))
            row = cursor.fetchone()
            chapter_id = row[0] if row else None
        if chapter_id is None:
            chapter_id = get_chapter_id(conn)

    cursor.execute(
        """
        INSERT INTO media (chapter_id, folder_id, document_id, name, media)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (chapter_id, folder_id, document_id, name, psycopg2.Binary(media_bytes))
    )
    conn.commit()