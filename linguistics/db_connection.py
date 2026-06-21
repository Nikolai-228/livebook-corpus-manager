# db_connection.py
# Общий модуль для подключения к базе данных

import psycopg2
from psycopg2 import sql
from psycopg2.extras import DictCursor

# Конфигурация подключения к БД
DB_CONFIG = {
    'host': 'livebook-team.duckdns.org',
    'port': 5432,
    'user': 'team_user',
    'password': 'book_live',
    'database': 'livebook_corpus'
}
def connect_db():
    """
    Создает и возвращает соединение с базой данных

    Returns:
        psycopg2.connection: Объект соединения с БД
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        raise
    except Exception as e:
        print(f"❌ Непредвиденная ошибка при подключении: {e}")
        raise


def get_db_connection():
    """
    Альтернативный метод для получения соединения с БД
    Использует DictCursor для доступа к данным по имени колонки
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.cursor_factory = DictCursor
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        raise


def test_connection():
    """
    Тестирует подключение к базе данных
    """
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            result = cur.fetchone()
            print("✅ Подключение к БД успешно!")
            print(f"   Версия PostgreSQL: {get_db_version()}")
            return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании подключения: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def get_db_version():
    """
    Возвращает версию PostgreSQL
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_table_info(table_name: str):
    """
    Получает информацию о структуре таблицы

    Args:
        table_name: Имя таблицы

    Returns:
        list: Список колонок с их типами
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            return cur.fetchall()
    finally:
        conn.close()


def execute_query(query: str, params=None):
    """
    Выполняет SQL-запрос и возвращает результат

    Args:
        query: SQL-запрос
        params: Параметры для запроса (опционально)

    Returns:
        list: Результат запроса
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)

            if query.strip().upper().startswith(('SELECT', 'SHOW', 'EXPLAIN')):
                return cur.fetchall()
            else:
                conn.commit()
                return cur.rowcount
    finally:
        conn.close()


def execute_query_dict(query: str, params=None):
    """
    Выполняет SQL-запрос и возвращает результат в виде словарей

    Args:
        query: SQL-запрос
        params: Параметры для запроса (опционально)

    Returns:
        list: Результат запроса в виде списка словарей
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)

            if query.strip().upper().startswith(('SELECT', 'SHOW', 'EXPLAIN')):
                return [dict(row) for row in cur.fetchall()]
            else:
                conn.commit()
                return cur.rowcount
    finally:
        conn.close()


# Список существующих таблиц
TABLES = {
    'documents': 'Документы',
    'documents_lemmatized': 'Лемматизированные документы',
    'chapters': 'Разделы',
    'bigrams': 'Биграммы',
    'trigrams': 'Триграммы',
    'collocations': 'Коллокации',
    'folders': 'Папки'
}


def get_all_tables():
    """
    Получает список всех таблиц в базе данных
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cur.fetchall()
            return [t[0] for t in tables]
    finally:
        conn.close()


def get_table_count(table_name: str):
    """
    Получает количество записей в таблице

    Args:
        table_name: Имя таблицы

    Returns:
        int: Количество записей
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_documents_by_chapter(chapter_id: int):
    """
    Получает все документы из конкретного раздела

    Args:
        chapter_id: ID раздела

    Returns:
        list: Список документов
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.type, dl.content
                FROM documents d
                INNER JOIN documents_lemmatized dl ON d.id = dl.id_documents
                WHERE d.chapter_id = %s AND dl.content IS NOT NULL AND dl.content != ''
                ORDER BY d.id
            """, (chapter_id,))
            return cur.fetchall()
    finally:
        conn.close()


def get_all_chapters():
    """
    Получает список всех разделов

    Returns:
        list: Список разделов (id, name)
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name
                FROM chapters
                ORDER BY id
            """)
            return cur.fetchall()
    finally:
        conn.close()


def get_document_content(doc_id: int):
    """
    Получает содержимое документа

    Args:
        doc_id: ID документа

    Returns:
        dict: Информация о документе
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT title, content, type, chapter_id
                FROM documents 
                WHERE id = %s
            """, (doc_id,))
            result = cur.fetchone()
            if result:
                return {
                    'title': result[0],
                    'content': result[1],
                    'type': result[2],
                    'chapter_id': result[3]
                }
            return None
    finally:
        conn.close()


def get_lemmatized_text(doc_id: int):
    """
    Получает лемматизированный текст документа

    Args:
        doc_id: ID документа

    Returns:
        str: Лемматизированный текст
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT content
                FROM documents_lemmatized 
                WHERE id_documents = %s
            """, (doc_id,))
            result = cur.fetchone()
            if result:
                return result[0]
            return None
    finally:
        conn.close()


if __name__ == "__main__":
    # Тестирование подключения
    print("🔍 ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К БД")
    print("=" * 60)

    if test_connection():
        print("\n📊 Информация о таблицах:")
        tables = get_all_tables()
        for table in tables:
            count = get_table_count(table)
            print(f"   - {table}: {count} записей")

        print("\n📚 Разделы:")
        chapters = get_all_chapters()
        for chapter_id, name in chapters:
            print(f"   - ID {chapter_id}: {name}")