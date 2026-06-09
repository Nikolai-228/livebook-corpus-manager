import psycopg2
from psycopg2 import sql
from nltk.tokenize import word_tokenize
from nltk.util import ngrams as nltk_ngrams
from pymorphy3 import MorphAnalyzer
import nltk
import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
import math
from rake_nltk import Rake

# Скачиваем необходимые данные для NLTK
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)

# Параметры подключения к БД
DB_CONFIG = {
    'host': 'livebook-team.duckdns.org',
    'port': 5432,
    'user': 'team_user',
    'password': 'book_live',
    'database': 'livebook_corpus'
}

# Русские стоп-слова
RUSSIAN_STOP_WORDS = {
    'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она', 'так', 'его', 'но',
    'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня',
    'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или',
    'ни', 'быть', 'чем', 'при', 'ведь', 'тоже', 'это', 'этого', 'этом', 'эти', 'этих', 'была',
    'были', 'было', 'будет', 'более', 'менее', 'самый', 'сама', 'сами', 'само', 'co', 'чтобы', 'для', 'без'
}

# Словарь для замены аббревиатур
ABBREVIATIONS = {
    'ИжГТУ': 'ижгту', 'ижгту': 'ижгту', 'ими': 'ими',
    'м-факультет': 'машиностроительный_факультет',
    'п-факультет': 'приборостроительный_факультет',
    'вт': 'вычислительная_техника',
    'омд': 'обработка_металлов_давлением',
    'эвм': 'электронно_вычислительная_машина',
    'ак': 'автомат_калашникова',
}

PROTECTED_WORDS = {'ижгту', 'ими', 'удмуртия', 'ижевск'}


def connect_db():
    """Создает и возвращает соединение с БД"""
    try:
        conn = psycopg2.connect(**DB_CONFIG, connect_timeout=60)
        return conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        raise


def preprocess_text(text: str) -> str:
    """Предобработка текста: замена аббревиатур"""
    if not text:
        return text
    result = text
    items = sorted(ABBREVIATIONS.items(), key=lambda x: len(x[0]), reverse=True)
    for abbr, full in items:
        pattern = r'\b' + re.escape(abbr) + r'\b'
        result = re.sub(pattern, full, result, flags=re.IGNORECASE)
    return result


def lemmatize_text(text: str, morph: MorphAnalyzer) -> Tuple[str, List[str]]:
    """Лемматизация текста, возвращает строку и список лемм"""
    if not text:
        return "", []

    text = preprocess_text(text)
    tokens = word_tokenize(text, language='russian')

    lemmas = []
    for token in tokens:
        token_lower = token.lower()

        if token_lower in PROTECTED_WORDS:
            lemmas.append(token_lower)
            continue

        if token.isalpha() and len(token) > 1:
            try:
                lemma = morph.normal_forms(token_lower)[0]
                if len(lemma) >= 2 and lemma not in RUSSIAN_STOP_WORDS:
                    lemmas.append(lemma)
            except Exception:
                pass

    return ' '.join(lemmas), lemmas


def create_tables(conn):
    """Создает все необходимые таблицы"""
    with conn.cursor() as cur:
        # Таблица для лемматизированного текста
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents_lemmatized (
                id SERIAL PRIMARY KEY,
                id_documents INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                content TEXT,
                unique_lemmas_count INTEGER DEFAULT 0,
                total_tokens_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_doc_id UNIQUE (id_documents)
            );
        """)

        # Таблица для униграмм
        cur.execute("""
            CREATE TABLE IF NOT EXISTS unigrams (
                id SERIAL PRIMARY KEY,
                id_documents INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                unigram TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                tf_idf_score FLOAT DEFAULT 0,
                contexts TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_unigram_doc UNIQUE (id_documents, unigram)
            );
            CREATE INDEX IF NOT EXISTS idx_unigrams_doc ON unigrams(id_documents);
            CREATE INDEX IF NOT EXISTS idx_unigrams_score ON unigrams(tf_idf_score DESC);
        """)

        # Таблица для биграмм
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bigrams (
                id SERIAL PRIMARY KEY,
                id_documents INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                bigram TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                contexts TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_bigram_doc UNIQUE (id_documents, bigram)
            );
            CREATE INDEX IF NOT EXISTS idx_bigrams_doc ON bigrams(id_documents);
        """)

        # Таблица для триграмм
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trigrams (
                id SERIAL PRIMARY KEY,
                id_documents INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                trigram TEXT NOT NULL,
                frequency INTEGER DEFAULT 1,
                contexts TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_trigram_doc UNIQUE (id_documents, trigram)
            );
            CREATE INDEX IF NOT EXISTS idx_trigrams_doc ON trigrams(id_documents);
        """)

        # Таблица для RAKE ключевых слов
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rake_keywords (
                id SERIAL PRIMARY KEY,
                id_documents INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                keyword TEXT NOT NULL,
                score FLOAT DEFAULT 0,
                contexts TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_rake_doc ON rake_keywords(id_documents);
            CREATE INDEX IF NOT EXISTS idx_rake_score ON rake_keywords(score DESC);
            CREATE INDEX IF NOT EXISTS idx_rake_keyword ON rake_keywords(keyword);
        """)

        conn.commit()
        print("Таблицы созданы/проверены")


def save_lemmatized(conn, doc_id, lemmatized_text, unique_lemmas, total_tokens):
    """Сохраняет лемматизированный текст"""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM documents_lemmatized WHERE id_documents = %s", (doc_id,))
        cur.execute("""
            INSERT INTO documents_lemmatized (id_documents, content, unique_lemmas_count, total_tokens_count)
            VALUES (%s, %s, %s, %s)
        """, (doc_id, lemmatized_text, unique_lemmas, total_tokens))
        conn.commit()


def get_global_term_frequencies(conn):
    """Получает глобальные частоты терминов для TF-IDF (один запрос)"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT unigram, COUNT(*) as doc_count 
            FROM unigrams 
            GROUP BY unigram
        """)
        return {row[0]: row[1] for row in cur.fetchall()}


def extract_unigrams_with_tfidf(conn, doc_id: int, lemmas: List[str], global_df: Dict[str, int], total_docs: int):
    """Извлекает униграммы с вычислением TF-IDF (оптимизированная версия)"""
    if not lemmas:
        return []

    term_freq = Counter(lemmas)
    unigrams = []

    for unigram, tf in term_freq.items():
        df = global_df.get(unigram, 1)
        idf = math.log((total_docs + 1) / (df + 1)) + 1
        tf_idf = tf * idf

        contexts = []
        for i, lemma in enumerate(lemmas):
            if lemma == unigram:
                start = max(0, i - 3)
                end = min(len(lemmas), i + 4)
                context_lemmas = lemmas[start:end]
                contexts.append(' '.join(context_lemmas))

        unigrams.append({
            'unigram': unigram,
            'frequency': tf,
            'tf_idf': tf_idf,
            'contexts': '||'.join(contexts[:5])
        })

    unigrams.sort(key=lambda x: x['tf_idf'], reverse=True)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM unigrams WHERE id_documents = %s", (doc_id,))
        for ug in unigrams[:50]:
            cur.execute("""
                INSERT INTO unigrams (id_documents, unigram, frequency, tf_idf_score, contexts)
                VALUES (%s, %s, %s, %s, %s)
            """, (doc_id, ug['unigram'], ug['frequency'], ug['tf_idf'], ug['contexts']))
        conn.commit()

    return unigrams[:30]


def extract_ngrams(conn, doc_id: int, lemmas: List[str], n: int, table_name: str):
    """Извлекает n-граммы (биграммы или триграммы)"""
    if len(lemmas) < n:
        return []

    ngram_freq = Counter()
    ngram_contexts = defaultdict(list)

    for i, ngram_tuple in enumerate(nltk_ngrams(lemmas, n)):
        ngram_text = ' '.join(ngram_tuple)
        words = ngram_text.split()
        if any(w in RUSSIAN_STOP_WORDS for w in words):
            continue
        ngram_freq[ngram_text] += 1

        if len(ngram_contexts[ngram_text]) < 3:
            start = max(0, i - 2)
            end = min(len(lemmas), i + n + 2)
            context_lemmas = lemmas[start:end]
            ngram_contexts[ngram_text].append(' '.join(context_lemmas))

    ngrams_data = []
    for ngram, freq in ngram_freq.items():
        if freq >= 2:
            ngrams_data.append({
                'ngram': ngram,
                'frequency': freq,
                'contexts': '||'.join(ngram_contexts[ngram][:3])
            })

    ngrams_data.sort(key=lambda x: x['frequency'], reverse=True)

    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table_name} WHERE id_documents = %s", (doc_id,))
        for ng in ngrams_data[:100]:
            cur.execute(f"""
                INSERT INTO {table_name} (id_documents, {table_name[:-1]}, frequency, contexts)
                VALUES (%s, %s, %s, %s)
            """, (doc_id, ng['ngram'], ng['frequency'], ng['contexts']))
        conn.commit()

    return ngrams_data[:30]


def extract_rake_keywords(conn, doc_id: int, text: str, lemmatized_text: str):
    """Извлекает ключевые слова с помощью RAKE"""
    if not text:
        return 0

    rake = Rake(language='russian', stopwords=RUSSIAN_STOP_WORDS, min_length=2, max_length=4)
    cleaned_text = re.sub(r'[^\w\s]', ' ', text)

    rake.extract_keywords_from_text(cleaned_text)
    ranked_phrases = rake.get_ranked_phrases_with_scores()

    with conn.cursor() as cur:
        cur.execute("DELETE FROM rake_keywords WHERE id_documents = %s", (doc_id,))

        lemmas_list = lemmatized_text.split() if lemmatized_text else []

        for score, phrase in ranked_phrases[:50]:
            if len(phrase.split()) > 4:
                continue

            # Ищем контекст фразы в лемматизированном тексте
            phrase_lower = phrase.lower()
            contexts = []

            # Поиск в исходном тексте для контекста
            text_lower = cleaned_text.lower()
            pos = 0
            while len(contexts) < 3:
                found = text_lower.find(phrase_lower, pos)
                if found == -1:
                    break
                start = max(0, found - 40)
                end = min(len(text), found + len(phrase) + 40)
                context = text[start:end].replace('\n', ' ').strip()
                contexts.append(f"...{context}...")
                pos = found + 1

            # Если не нашли в исходном тексте, ищем в леммах
            if not contexts and lemmas_list:
                phrase_words = phrase_lower.split()
                for i in range(len(lemmas_list) - len(phrase_words) + 1):
                    if lemmas_list[i:i + len(phrase_words)] == phrase_words:
                        start = max(0, i - 3)
                        end = min(len(lemmas_list), i + len(phrase_words) + 3)
                        context = ' '.join(lemmas_list[start:end])
                        contexts.append(f"...{context}...")
                        if len(contexts) >= 2:
                            break

            cur.execute("""
                INSERT INTO rake_keywords (id_documents, keyword, score, contexts)
                VALUES (%s, %s, %s, %s)
            """, (doc_id, phrase, score, '||'.join(contexts[:3]) if contexts else ''))

        conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM rake_keywords WHERE id_documents = %s", (doc_id,))
        return cur.fetchone()[0]


def process_all_documents(conn, morph: MorphAnalyzer):
    """Обрабатывает все документы"""
    print("Загрузка документов...")
    with conn.cursor() as cur:
        cur.execute("SELECT id, content FROM documents WHERE content IS NOT NULL AND content != ''")
        documents = cur.fetchall()

    print(f"Найдено документов: {len(documents)}")

    # Сначала сохраняем все лемматизированные тексты
    all_lemmas_data = {}
    print("\n--- Этап 1: Лемматизация всех документов ---")

    for i, (doc_id, content) in enumerate(documents):
        if content:
            lemmatized_text, lemmas = lemmatize_text(content, morph)
            unique_lemmas = len(set(lemmas))
            total_tokens = len(lemmas)
            save_lemmatized(conn, doc_id, lemmatized_text, unique_lemmas, total_tokens)
            all_lemmas_data[doc_id] = lemmas
            print(f"   Документ {doc_id}: лемматизирован ({unique_lemmas} уникальных лемм, {total_tokens} токенов)")

            if (i + 1) % 50 == 0:
                print(f"   --- Обработано {i + 1} документов ---")

    print("\n--- Этап 2: Извлечение n-грамм и ключевых слов ---")

    # Получаем глобальные частоты для TF-IDF (один раз для всех)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents_lemmatized")
        total_docs = max(1, cur.fetchone()[0])

    processed = 0
    for doc_id, lemmas in all_lemmas_data.items():
        if lemmas:
            print(f"\n--- Обработка документа ID: {doc_id} ---")

            # Получаем глобальные частоты для этого документа
            # Временно вычисляем частоты для всех слов в этом документе
            term_freq_in_doc = Counter(lemmas)

            # Для TF-IDF нужны глобальные частоты - получаем их из базы
            global_df = {}
            with conn.cursor() as cur:
                for word in set(lemmas):
                    cur.execute("SELECT COUNT(*) FROM documents_lemmatized WHERE content LIKE %s", (f'%{word}%',))
                    global_df[word] = max(1, cur.fetchone()[0])

            # Униграммы
            unigrams = extract_unigrams_with_tfidf(conn, doc_id, lemmas, global_df, total_docs)
            print(f"   ✅ Униграммы: {len(unigrams)} уникальных слов")

            # Биграммы
            bigrams = extract_ngrams(conn, doc_id, lemmas, 2, 'bigrams')
            print(f"   ✅ Биграммы: {len(bigrams)} уникальных пар")

            # Триграммы
            trigrams = extract_ngrams(conn, doc_id, lemmas, 3, 'trigrams')
            print(f"   ✅ Триграммы: {len(trigrams)} уникальных троек")

            # Получаем исходный текст для RAKE
            with conn.cursor() as cur:
                cur.execute("SELECT content FROM documents WHERE id = %s", (doc_id,))
                original_text = cur.fetchone()[0]

            # RAKE ключевые слова
            rake_count = extract_rake_keywords(conn, doc_id, original_text, ' '.join(lemmas))
            print(f"   ✅ RAKE ключевые слова: {rake_count}")

            processed += 1
            if processed % 10 == 0:
                print(f"\n--- Всего обработано {processed} документов ---")

    print(f"\n✅ Обработка завершена! Обработано {processed} документов.")


def get_document_ngrams(conn, doc_id: int):
    """Получает все n-граммы для документа"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT unigram, frequency, tf_idf_score, contexts 
            FROM unigrams 
            WHERE id_documents = %s 
            ORDER BY tf_idf_score DESC 
            LIMIT 15
        """, (doc_id,))
        unigrams = cur.fetchall()

        cur.execute("""
            SELECT bigram, frequency, contexts 
            FROM bigrams 
            WHERE id_documents = %s 
            ORDER BY frequency DESC 
            LIMIT 15
        """, (doc_id,))
        bigrams = cur.fetchall()

        cur.execute("""
            SELECT trigram, frequency, contexts 
            FROM trigrams 
            WHERE id_documents = %s 
            ORDER BY frequency DESC 
            LIMIT 10
        """, (doc_id,))
        trigrams = cur.fetchall()

        cur.execute("""
            SELECT keyword, score, contexts 
            FROM rake_keywords 
            WHERE id_documents = %s 
            ORDER BY score DESC 
            LIMIT 15
        """, (doc_id,))
        rake_keywords = cur.fetchall()

        return unigrams, bigrams, trigrams, rake_keywords


def display_ngrams_for_document(conn, doc_id: int):
    """Отображает n-граммы для конкретного документа"""
    with conn.cursor() as cur:
        cur.execute("SELECT title FROM documents WHERE id = %s", (doc_id,))
        title = cur.fetchone()
        title_text = title[0] if title else "Без названия"

    print(f"\n{'=' * 80}")
    print(f"📄 ДОКУМЕНТ ID: {doc_id}")
    print(f"   Название: {title_text[:100]}")
    print(f"{'=' * 80}")

    unigrams, bigrams, trigrams, rake_keywords = get_document_ngrams(conn, doc_id)

    print(f"\n🔑 УНИГРАММЫ (ключевые слова по TF-IDF):")
    for unigram, freq, tfidf, contexts in unigrams:
        print(f"   • {unigram} (частота: {freq}, TF-IDF: {tfidf:.4f})")
        if contexts:
            ctx = contexts.split('||')[0][:100] if contexts else ""
            if ctx:
                print(f"     Контекст: ...{ctx}...")

    print(f"\n📚 БИГРАММЫ (популярные пары слов):")
    for bigram, freq, contexts in bigrams:
        print(f"   • \"{bigram}\" (встречается {freq} раз)")
        if contexts:
            ctx = contexts.split('||')[0][:100] if contexts else ""
            if ctx:
                print(f"     Контекст: ...{ctx}...")

    print(f"\n📚 ТРИГРАММЫ (популярные тройки слов):")
    for trigram, freq, contexts in trigrams:
        print(f"   • \"{trigram}\" (встречается {freq} раз)")
        if contexts:
            ctx = contexts.split('||')[0][:100] if contexts else ""
            if ctx:
                print(f"     Контекст: ...{ctx}...")

    if rake_keywords:
        print(f"\n🎯 КЛЮЧЕВЫЕ СЛОВА (RAKE):")
        for keyword, score, contexts in rake_keywords:
            print(f"   • \"{keyword}\" (релевантность: {score:.3f})")
            if contexts:
                ctx = contexts.split('||')[0][:100] if contexts else ""
                if ctx:
                    print(f"     Контекст: ...{ctx}...")


def get_statistics(conn):
    """Получает статистику по всем n-граммам"""
    with conn.cursor() as cur:
        stats = {}

        cur.execute("SELECT COUNT(DISTINCT unigram), SUM(frequency) FROM unigrams")
        stats['unigrams'] = cur.fetchone()

        cur.execute("SELECT COUNT(DISTINCT bigram), SUM(frequency) FROM bigrams")
        stats['bigrams'] = cur.fetchone()

        cur.execute("SELECT COUNT(DISTINCT trigram), SUM(frequency) FROM trigrams")
        stats['trigrams'] = cur.fetchone()

        cur.execute("SELECT COUNT(DISTINCT keyword) FROM rake_keywords")
        stats['rake_keywords'] = cur.fetchone()[0]

        return stats


def main():
    print("Инициализация анализатора pymorphy3...")
    morph = MorphAnalyzer()

    print("Подключение к БД...")
    conn = connect_db()

    try:
        create_tables(conn)
        process_all_documents(conn, morph)

        print(f"\n{'=' * 80}")
        print("ДЕМОНСТРАЦИЯ РЕЗУЛЬТАТОВ")
        print(f"{'=' * 80}")

        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT id_documents FROM unigrams ORDER BY id_documents LIMIT 5")
            doc_ids = [row[0] for row in cur.fetchall()]

        for doc_id in doc_ids:
            display_ngrams_for_document(conn, doc_id)

        stats = get_statistics(conn)
        print(f"\n{'=' * 80}")
        print("📊 ОБЩАЯ СТАТИСТИКА ПО БАЗЕ ДАННЫХ")
        print(f"{'=' * 80}")
        print(f"   Уникальные униграммы: {stats['unigrams'][0]}, всего вхождений: {stats['unigrams'][1]}")
        print(f"   Уникальные биграммы: {stats['bigrams'][0]}, всего вхождений: {stats['bigrams'][1]}")
        print(f"   Уникальные триграммы: {stats['trigrams'][0]}, всего вхождений: {stats['trigrams'][1]}")
        print(f"   Уникальные ключевые слова (RAKE): {stats['rake_keywords']}")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()