import psycopg2
from nltk.collocations import BigramCollocationFinder
from nltk.corpus import stopwords
import nltk
import re

# Скачиваем стоп-слова если не скачаны
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('stopwords', quiet=True)

# Конфигурация БД
DB_CONFIG = {
    'host': 'livebook-team.duckdns.org',
    'port': 5432,
    'user': 'team_user',
    'password': 'book_live',
    'database': 'livebook_corpus'
}

RUSSIAN_STOP_WORDS = set(stopwords.words('russian'))


def connect_db():
    """Подключение к БД"""
    return psycopg2.connect(**DB_CONFIG)


def create_bigrams_table(conn):
    """Создаёт таблицу new_bigrams, если её нет"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS new_bigrams (
                id SERIAL PRIMARY KEY,
                id_documents INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                bigram TEXT NOT NULL,
                word1 TEXT NOT NULL,
                word2 TEXT NOT NULL,
                frequency INTEGER DEFAULT 0,
                contexts TEXT
            );
        """)

        # Индексы для быстрого поиска
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_new_bigrams_doc ON new_bigrams(id_documents);
            CREATE INDEX IF NOT EXISTS idx_new_bigrams_text ON new_bigrams(bigram);
            CREATE INDEX IF NOT EXISTS idx_new_bigrams_word1 ON new_bigrams(word1);
            CREATE INDEX IF NOT EXISTS idx_new_bigrams_word2 ON new_bigrams(word2);
        """)

        conn.commit()
        print("✅ Таблица new_bigrams создана/проверена")


def get_documents_with_lemmas(conn):
    """Получает все документы с лемматизированным текстом"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT d.id, d.title, d.type, d.chapter_id, dl.content
            FROM documents d
            INNER JOIN documents_lemmatized dl ON d.id = dl.id_documents
            WHERE dl.content IS NOT NULL AND dl.content != ''
            ORDER BY d.id
        """)
        return cur.fetchall()


def find_all_contexts(text: str, word1: str, word2: str, context_size: int = 60) -> list:
    """
    Находит ВСЕ контексты для биграммы в лемматизированном тексте
    """
    contexts = []
    text_lower = text.lower()
    pattern = f"{word1.lower()} {word2.lower()}"
    pos = 0

    while True:
        found = text_lower.find(pattern, pos)
        if found == -1:
            break
        start = max(0, found - context_size)
        end = min(len(text), found + len(pattern) + context_size)
        context = text[start:end].replace('\n', ' ')
        contexts.append(context.strip())
        pos = found + 1

    return contexts


def build_bigrams(conn, top_n_per_doc: int = 10):
    """
    Вычисляет топ-N биграмм по частоте для каждого документа
    и сохраняет в таблицу new_bigrams
    """
    print("🔄 Начинаем построение биграмм по частоте...")
    print(f"   Сохраняется топ-{top_n_per_doc} биграмм на документ")

    # Удаляем старые данные
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE new_bigrams RESTART IDENTITY CASCADE")
        conn.commit()
        print("🗑️ Старые данные удалены")

    # Получаем все документы
    documents = get_documents_with_lemmas(conn)
    total_docs = len(documents)
    print(f"📁 Найдено документов с лемматизированным текстом: {total_docs}")

    processed = 0
    total_bigrams = 0

    for doc_id, title, doc_type, chapter_id, lemmatized_text in documents:
        if not lemmatized_text:
            continue

        # Разбиваем лемматизированный текст на леммы
        lemmas = lemmatized_text.lower().split()

        # Фильтруем стоп-слова и короткие слова
        lemmas = [l for l in lemmas if l not in RUSSIAN_STOP_WORDS and len(l) > 1]

        if len(lemmas) < 2:
            continue

        # Находим биграммы
        finder = BigramCollocationFinder.from_words(lemmas)
        finder.apply_freq_filter(1)  # Минимум 1 вхождение

        # Получаем все биграммы с частотами
        bigram_freq = finder.ngram_fd

        if not bigram_freq:
            continue

        # Сортируем по частоте (от большей к меньшей) и берём топ-N
        sorted_bigrams = sorted(bigram_freq.items(), key=lambda x: x[1], reverse=True)[:top_n_per_doc]

        # Подготавливаем данные для массовой вставки
        data = []
        for (w1, w2), freq in sorted_bigrams:
            bigram_text = f"{w1} {w2}"

            # Находим ВСЕ контексты для биграммы
            contexts = find_all_contexts(lemmatized_text, w1, w2)
            contexts_str = '||'.join(contexts) if contexts else ''

            data.append((doc_id, bigram_text, w1, w2, freq, contexts_str))

        # Массовая вставка (быстрее, чем по одному INSERT)
        if data:
            with conn.cursor() as cur:
                cur.executemany("""
                    INSERT INTO new_bigrams 
                    (id_documents, bigram, word1, word2, frequency, contexts)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, data)
                conn.commit()

            total_bigrams += len(data)

        processed += 1
        if processed % 10 == 0:
            print(f"   Обработано {processed} из {total_docs} документов... (сохранено биграмм: {total_bigrams})")

    print(f"\n✅ Готово! Обработано {processed} документов.")
    print(f"📊 Сохранено биграмм: {total_bigrams}")
    print(f"📊 В среднем {total_bigrams / max(1, processed):.1f} биграмм на документ")


def main():
    print("=" * 70)
    print("🔧 ПОСТРОЕНИЕ ТАБЛИЦЫ БИГРАММ (ТОП-10 ПО ЧАСТОТЕ)")
    print("=" * 70)

    conn = connect_db()
    try:
        create_bigrams_table(conn)
        build_bigrams(conn, top_n_per_doc=10)

        # Проверка результата
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM new_bigrams")
            count = cur.fetchone()[0]
            print(f"\n📊 В таблице new_bigrams записей: {count}")

            cur.execute("""
                SELECT COUNT(DISTINCT id_documents) FROM new_bigrams
            """)
            docs_count = cur.fetchone()[0]
            print(f"📄 Документов с биграммами: {docs_count}")

            # Показываем пример для проверки
            cur.execute("""
                SELECT d.id, d.title, COUNT(b.id) as bigram_count
                FROM documents d
                INNER JOIN new_bigrams b ON d.id = b.id_documents
                GROUP BY d.id, d.title
                ORDER BY bigram_count DESC
                LIMIT 3
            """)
            print(f"\n📊 Топ-3 документа по количеству биграмм:")
            for doc_id, title, count in cur.fetchall():
                print(f"   ID: {doc_id}, Название: {title[:50]}, Биграмм: {count}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()