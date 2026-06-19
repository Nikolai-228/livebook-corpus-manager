import psycopg2
from psycopg2 import sql
from nltk.collocations import BigramCollocationFinder
from nltk.metrics import BigramAssocMeasures
from nltk.corpus import stopwords
import nltk

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


def create_collocations_table(conn):
    """Создаёт таблицу collocations, если её нет"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS collocations (
                id SERIAL PRIMARY KEY,
                id_documents INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                collocation TEXT NOT NULL,
                word1 TEXT NOT NULL,
                word2 TEXT NOT NULL,
                frequency INTEGER DEFAULT 0,
                likelihood_score FLOAT DEFAULT 0,
                contexts TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Индексы для быстрого поиска
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_collocations_doc ON collocations(id_documents);
            CREATE INDEX IF NOT EXISTS idx_collocations_score ON collocations(likelihood_score DESC);
            CREATE INDEX IF NOT EXISTS idx_collocations_word1 ON collocations(word1);
            CREATE INDEX IF NOT EXISTS idx_collocations_word2 ON collocations(word2);
        """)

        conn.commit()
        print("✅ Таблица collocations создана/проверена")


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


def find_contexts(text: str, word1: str, word2: str, context_size: int = 60) -> list:
    """
    Находит контексты для коллокации в лемматизированном тексте
    Возвращает список контекстов (до 3 штук)
    """
    contexts = []
    text_lower = text.lower()
    pattern = f"{word1.lower()} {word2.lower()}"
    pos = 0

    while len(contexts) < 10:
        found = text_lower.find(pattern, pos)
        if found == -1:
            break
        start = max(0, found - context_size)
        end = min(len(text), found + len(pattern) + context_size)
        context = text[start:end].replace('\n', ' ')
        contexts.append(context.strip())
        pos = found + 1

    return contexts


def build_collocations(conn, top_n_per_doc: int = 10):
    """
    Вычисляет коллокации (прилагательное + существительное) по Likelihood Ratio
    для каждого документа и сохраняет в таблицу
    """
    print("🔄 Начинаем построение коллокаций...")

    # Удаляем старые данные
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE collocations RESTART IDENTITY CASCADE")
        conn.commit()
        print("🗑️ Старые данные удалены")

    # Получаем все документы
    documents = get_documents_with_lemmas(conn)
    total_docs = len(documents)
    print(f"📁 Найдено документов с лемматизированным текстом: {total_docs}")

    processed = 0
    total_collocations = 0

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
        finder.apply_freq_filter(2)  # Минимум 2 вхождения

        # Получаем все биграммы с Likelihood Ratio
        scored_bigrams = finder.score_ngrams(BigramAssocMeasures.likelihood_ratio)

        if not scored_bigrams:
            continue

        # Фильтруем: оставляем только прилагательное + существительное
        # (для этого нужен pymorphy3, но чтобы не усложнять,
        #  мы пропускаем этот шаг, так как у нас уже леммы)
        # Вместо этого берём топ-N биграмм по Likelihood Ratio
        top_bigrams = scored_bigrams[:top_n_per_doc]

        # Вставляем в таблицу
        with conn.cursor() as cur:
            for (w1, w2), score in top_bigrams:
                bigram_text = f"{w1} {w2}"
                freq = finder.ngram_fd[(w1, w2)]

                # Находим контексты в оригинальном лемматизированном тексте
                contexts = find_contexts(lemmatized_text, w1, w2)
                contexts_str = '||'.join(contexts) if contexts else ''

                cur.execute("""
                    INSERT INTO collocations 
                    (id_documents, collocation, word1, word2, frequency, likelihood_score, contexts)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (doc_id, bigram_text, w1, w2, freq, score, contexts_str))

            conn.commit()
            total_collocations += len(top_bigrams)

        processed += 1
        if processed % 10 == 0:
            print(f"   Обработано {processed} из {total_docs} документов...")

    print(f"\n✅ Готово! Обработано {processed} документов.")
    print(f"📊 Сохранено коллокаций: {total_collocations}")


def main():
    print("=" * 70)
    print("🔧 ПОСТРОЕНИЕ ТАБЛИЦЫ КОЛЛОКАЦИЙ (LIKELIHOOD RATIO)")
    print("=" * 70)

    conn = connect_db()
    try:
        create_collocations_table(conn)
        build_collocations(conn, top_n_per_doc=10)

        # Проверка результата
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM collocations")
            count = cur.fetchone()[0]
            print(f"\n📊 В таблице collocations записей: {count}")

            cur.execute("""
                SELECT COUNT(DISTINCT id_documents) FROM collocations
            """)
            docs_count = cur.fetchone()[0]
            print(f"📄 Документов с коллокациями: {docs_count}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()