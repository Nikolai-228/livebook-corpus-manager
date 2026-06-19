# parser/db_utils.py
import psycopg2
from urllib.parse import urlparse
from config import DATABASE_DSN, CHAPTERS


# ==========================================================
# 1. ПОДКЛЮЧЕНИЕ
# ==========================================================

def get_db_connection():
    """Создаёт подключение к PostgreSQL"""
    parsed = urlparse(DATABASE_DSN)

    conn = psycopg2.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname or 'localhost',
        port=parsed.port or 5432,
        database=parsed.path[1:] if parsed.path else 'test_book'
    )
    return conn


# ==========================================================
# 2. РАЗДЕЛЫ (CHAPTERS)
# ==========================================================

def get_or_create_chapter(conn, chapter_name: str) -> int:
    """
    Возвращает ID раздела по имени.
    Если раздела нет — создаёт.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM chapters WHERE name = %s", (chapter_name,))
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute("INSERT INTO chapters (name) VALUES (%s) RETURNING id", (chapter_name,))
        conn.commit()
        return cur.fetchone()[0]


def init_chapters_from_config(conn):
    """Инициализирует все разделы из config.py"""
    for chapter in CHAPTERS:
        name = chapter["name"]
        get_or_create_chapter(conn, name)
        print(f"   ✅ Раздел: {name}")


def get_chapter_id(conn, chapter_name: str) -> int:
    """Возвращает ID раздела. Если нет — создаёт."""
    return get_or_create_chapter(conn, chapter_name)


# ==========================================================
# 3. ПАПКИ (FOLDERS)
# ==========================================================

def get_or_create_folder(
        conn,
        folder_name: str,
        chapter_id: int,
        parent_db_id: int = None,
        full_path: str = None
) -> int:
    """
    Создаёт или возвращает папку.

    Параметры:
    - folder_name: имя папки
    - chapter_id: ID раздела (обязателен)
    - parent_db_id: ID родительской папки (может быть None)
    - full_path: полный путь (если None — формируется из folder_name)
    """
    with conn.cursor() as cur:
        # Поиск существующей папки
        if parent_db_id:
            cur.execute("""
                SELECT id FROM folders 
                WHERE name = %s AND parent_folder_id = %s AND chapter_id = %s
            """, (folder_name, parent_db_id, chapter_id))
        else:
            cur.execute("""
                SELECT id FROM folders 
                WHERE name = %s AND parent_folder_id IS NULL AND chapter_id = %s
            """, (folder_name, chapter_id))

        row = cur.fetchone()
        if row:
            return row[0]

        # Создаём новую папку
        if full_path is None:
            full_path = folder_name

        cur.execute("""
            INSERT INTO folders (name, parent_folder_id, full_path, chapter_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (folder_name, parent_db_id, full_path, chapter_id))
        conn.commit()
        return cur.fetchone()[0]


def get_folder_by_path(conn, full_path: str, chapter_id: int) -> int:
    """Возвращает ID папки по полному пути"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id FROM folders
            WHERE full_path = %s AND chapter_id = %s
        """, (full_path, chapter_id))
        row = cur.fetchone()
        return row[0] if row else None


# ==========================================================
# 4. ДОКУМЕНТЫ (DOCUMENTS)
# ==========================================================

def save_document(
        conn,
        title: str,
        file_type: str,
        chapter_id: int,
        folder_id: int = None,
        content: str = None,
        url: str = None
) -> int:
    """
    Сохраняет документ в БД.

    Параметры:
    - title: название документа
    - file_type: тип файла (pdf, docx, google_doc и т.д.)
    - chapter_id: ID раздела (обязателен)
    - folder_id: ID папки (может быть None)
    - content: текст документа (может быть None)
    - url: ссылка на Google Drive

    Возвращает ID созданного документа.
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO documents (title, type, chapter_id, folder_id, content, url)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (title, file_type, chapter_id, folder_id, content, url))
        conn.commit()
        return cur.fetchone()[0]


def get_document(conn, doc_id: int) -> dict:
    """Возвращает информацию о документе по ID"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, type, chapter_id, folder_id, content, url
            FROM documents WHERE id = %s
        """, (doc_id,))
        row = cur.fetchone()
        if row:
            return {
                'id': row[0],
                'title': row[1],
                'type': row[2],
                'chapter_id': row[3],
                'folder_id': row[4],
                'content': row[5],
                'url': row[6]
            }
        return None


def update_document_content(conn, doc_id: int, content: str):
    """Обновляет content документа"""
    with conn.cursor() as cur:
        cur.execute("UPDATE documents SET content = %s WHERE id = %s", (content, doc_id))
        conn.commit()


def update_document_title(conn, doc_id: int, title: str):
    """Обновляет title документа"""
    with conn.cursor() as cur:
        cur.execute("UPDATE documents SET title = %s WHERE id = %s", (title, doc_id))
        conn.commit()


# ==========================================================
# 5. МЕДИАФАЙЛЫ (MEDIA)
# ==========================================================

def save_media(
        conn,
        chapter_id: int,
        name: str,
        media_bytes: bytes,
        folder_id: int = None,
        document_id: int = None
) -> int:
    """
    Сохраняет медиафайл (изображение) в БД.

    Параметры:
    - chapter_id: ID раздела (обязателен)
    - name: имя файла
    - media_bytes: содержимое файла в байтах
    - folder_id: ID папки (может быть None)
    - document_id: ID документа (может быть None)

    Возвращает ID созданной записи.
    """
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO media (chapter_id, folder_id, document_id, name, media)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (chapter_id, folder_id, document_id, name, psycopg2.Binary(media_bytes)))
        conn.commit()
        return cur.fetchone()[0]


# ==========================================================
# 6. ОЧИСТКА БД
# ==========================================================

def clear_database(conn):
    """
    Удаляет все данные из таблиц chapters, folders, documents, media.
    Сбрасывает счётчики ID.
    """
    print("\n🗑️ ОЧИСТКА БАЗЫ ДАННЫХ...")

    with conn.cursor() as cur:
        # Удаляем в правильном порядке (из-за внешних ключей)
        cur.execute("TRUNCATE TABLE media CASCADE")
        cur.execute("TRUNCATE TABLE documents CASCADE")
        cur.execute("TRUNCATE TABLE folders CASCADE")
        cur.execute("TRUNCATE TABLE chapters CASCADE")
        conn.commit()

    print("   ✅ Все данные удалены")

    # Сброс последовательностей (чтобы ID начинались с 1)
    with conn.cursor() as cur:
        cur.execute("ALTER SEQUENCE chapters_id_seq RESTART WITH 1")
        cur.execute("ALTER SEQUENCE folders_id_seq RESTART WITH 1")
        cur.execute("ALTER SEQUENCE documents_id_seq RESTART WITH 1")
        cur.execute("ALTER SEQUENCE media_id_seq RESTART WITH 1")
        conn.commit()

    print("   ✅ Счётчики сброшены")


# ==========================================================
# 7. СТАТИСТИКА
# ==========================================================

def get_stats(conn) -> dict:
    """Возвращает статистику по первым 4 таблицам"""
    with conn.cursor() as cur:
        stats = {}

        cur.execute("SELECT COUNT(*) FROM chapters")
        stats['chapters'] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM folders")
        stats['folders'] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM documents")
        stats['documents'] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM media")
        stats['media'] = cur.fetchone()[0]

        return stats


def print_stats(conn):
    """Выводит статистику в консоль"""
    stats = get_stats(conn)

    print("\n" + "=" * 60)
    print("📊 СТАТИСТИКА БАЗЫ ДАННЫХ")
    print("=" * 60)
    print(f"   📚 Разделов: {stats['chapters']}")
    print(f"   📁 Папок: {stats['folders']}")
    print(f"   📄 Документов: {stats['documents']}")
    print(f"   🖼️ Изображений: {stats['media']}")


# ==========================================================
# 8. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================================

def get_documents_by_chapter(conn, chapter_id: int) -> list:
    """Возвращает все документы раздела"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, type, folder_id, url
            FROM documents
            WHERE chapter_id = %s
            ORDER BY id
        """, (chapter_id,))
        return cur.fetchall()


def get_documents_by_folder(conn, folder_id: int) -> list:
    """Возвращает все документы в папке"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, type, url
            FROM documents
            WHERE folder_id = %s
            ORDER BY id
        """, (folder_id,))
        return cur.fetchall()


def get_documents_need_cleanup(conn, limit: int = None) -> list:
    """
    Возвращает документы, которые нуждаются в очистке:
    - content содержит URL или сноски
    - title начинается с чисел
    """
    with conn.cursor() as cur:
        query = """
            SELECT id, title, content, type
            FROM documents
            WHERE content IS NOT NULL
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"
        cur.execute(query)
        return cur.fetchall()


# ==========================================================
# 9. ТЕСТ
# ==========================================================

if __name__ == "__main__":
    conn = get_db_connection()

    print("📊 Статистика БД:")
    print_stats(conn)

    # Проверка структуры
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_name IN ('chapters', 'folders', 'documents', 'media')
            ORDER BY table_name, ordinal_position
        """)
        columns = cur.fetchall()

        print("\n📋 СТРУКТУРА ТАБЛИЦ:")
        for table, column, dtype in columns:
            print(f"   {table}.{column}: {dtype}")

    conn.close()