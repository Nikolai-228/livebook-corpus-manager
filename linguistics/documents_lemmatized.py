import psycopg2
from psycopg2 import sql
from nltk.tokenize import word_tokenize
from pymorphy3 import MorphAnalyzer
import nltk
import re
from collections import Counter

# Скачиваем необходимые данные для NLTK (если не скачаны)
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

# Словарь для замены аббревиатур и специальных слов
ABBREVIATIONS = {
    # Названия учебных заведений
    'ИжГТУ': 'ижгту',
    'ижгту': 'ижгту',
    'ижгту им': 'ижгту',
    'ими': 'ими',

    # Факультеты
    'м-факультет': 'машиностроительный_факультет',
    'п-факультет': 'приборостроительный_факультет',
    'мт-факультет': 'механико_технологический_факультет',
    'ис-факультет': 'инженерно_строительный_факультет',

    # Кафедры
    'омд': 'обработка_металлов_давлением',
    'тмм': 'теория_машин_и_механизмов',
    'кпу': 'конструирование_приборов_и_устройств',
    'вт': 'вычислительная_техника',
    'эип': 'экономика_и_промышленность',
    'пгс': 'промышленное_и_гражданское_строительство',
    'кра': 'конструирование_радиоаппаратуры',

    # Организации
    'нити': 'научно_исследовательский_технологический_институт',
    'инимит': 'институт_металлургии_и_технологии',
    'октб': 'особое_конструкторско_технологическое_бюро',
    'сни': 'студенческий_научно_исследовательский_институт',

    # Технические термины
    'эвм': 'электронно_вычислительная_машина',
    'ак': 'автомат_калашникова',
    'ак-47': 'автомат_калашникова',
    'рдтт': 'ракетный_двигатель_твердого_топлива',
    'тмо': 'термомеханическая_обработка',
    'втмо': 'высокотемпературная_термомеханическая_обработка',
    'чпу': 'числовое_программное_управление',
    'пуазо': 'прибор_управления_артиллерийским_зенитным_огнем',

    # Должности и звания
    'д.т.н': 'доктор_технических_наук',
    'к.т.н': 'кандидат_технических_наук',
    'проф': 'профессор',
    'доц': 'доцент',

    # Спортивные термины
    'ссо': 'студенческий_строительный_отряд',
    'куб': 'коммунистическая_ударная_бригада',
    'стэм': 'студенческий_театр_эстрадных_миниатюр',

    # Другое
    'вов': 'великая_отечественная_война',
    'влксм': 'всесоюзный_ленинский_коммунистический_союз_молодежи',
    'кпсс': 'коммунистическая_партия_советского_союза',
    'удмуртия': 'удмуртия',
    'ижевск': 'ижевск',
}

# Слова слов, которые НЕ нужно лемматизировать (сохраняем как есть)
PROTECTED_WORDS = { 'ижгту' }


def preprocess_text(text):
    """Предобработка текста: замена аббревиатур"""
    if not text:
        return text

    result = text

    # Сортируем по длине ключа (от длинных к коротким) для корректной замены
    items = sorted(ABBREVIATIONS.items(), key=lambda x: len(x[0]), reverse=True)

    for abbr, full in items:
        pattern = r'\b' + re.escape(abbr) + r'\b'
        result = re.sub(pattern, full, result, flags=re.IGNORECASE)

    return result


def connect_db():
    """Создает и возвращает соединение с БД"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Ошибка подключения к БД: {e}")
        raise


def create_lemmatized_table(conn):
    """Создает таблицу для хранения лемматизированного текста"""
    with conn.cursor() as cur:
        # Проверяем, существует ли таблица
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'documents_lemmatized'
            )
        """)
        table_exists = cur.fetchone()[0]

        if not table_exists:
            # Создаем новую таблицу
            cur.execute("""
                CREATE TABLE documents_lemmatized (
                    id SERIAL PRIMARY KEY,
                    id_documents INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    content TEXT,
                    unique_lemmas_count INTEGER DEFAULT 0,
                    total_tokens_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_lemmatized_doc_id ON documents_lemmatized(id_documents);
            """)
            print("Таблица documents_lemmatized создана")
        else:
            # Проверяем, есть ли нужные столбцы
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'documents_lemmatized' 
                AND column_name IN ('unique_lemmas_count', 'total_tokens_count')
            """)
            existing_columns = [row[0] for row in cur.fetchall()]

            if 'unique_lemmas_count' not in existing_columns:
                cur.execute("ALTER TABLE documents_lemmatized ADD COLUMN unique_lemmas_count INTEGER DEFAULT 0")
                print("Добавлен столбец unique_lemmas_count")

            if 'total_tokens_count' not in existing_columns:
                cur.execute("ALTER TABLE documents_lemmatized ADD COLUMN total_tokens_count INTEGER DEFAULT 0")
                print("Добавлен столбец total_tokens_count")

            # Удаляем старые столбцы, если они были (для совместимости)
            if 'lemmas_count' in existing_columns:
                cur.execute("ALTER TABLE documents_lemmatized DROP COLUMN IF EXISTS lemmas_count")
                print("Удален устаревший столбец lemmas_count")
            if 'tokens_count' in existing_columns:
                cur.execute("ALTER TABLE documents_lemmatized DROP COLUMN IF EXISTS tokens_count")
                print("Удален устаревший столбец tokens_count")

        conn.commit()


def fetch_documents(conn):
    """Получает все документы из таблицы documents"""
    with conn.cursor() as cur:
        cur.execute("SELECT id, content FROM documents WHERE content IS NOT NULL AND content != ''")
        return cur.fetchall()


def lemmatize_text(text, morph):
    """Лемматизирует переданный текст с предобработкой и защитой слов.
       Возвращает кортеж (лемматизированный_текст, количество_уникальных_лемм, общее_количество_токенов)"""
    if not text or not isinstance(text, str):
        return "", 0, 0

    # Предобработка: замена аббревиатур и сокращений
    text = preprocess_text(text)

    # Токенизация
    tokens = word_tokenize(text, language='russian')

    # Лемматизация с защитой определенных слов
    lemmas_list = []
    total_tokens = 0

    for token in tokens:
        token_lower = token.lower()

        # Если слово в защищенном списке или это аббревиатура с подчеркиваниями
        if token_lower in PROTECTED_WORDS or '_' in token:
            lemmas_list.append(token_lower)
            total_tokens += 1
            continue

        # Оставляем только буквы (убираем знаки пунктуации)
        if token.isalpha():
            total_tokens += 1
            try:
                lemma = morph.normal_forms(token_lower)[0]
                if len(lemma) < 2:
                    lemmas_list.append(token_lower)
                else:
                    lemmas_list.append(lemma)
            except Exception:
                lemmas_list.append(token_lower)
        # Для небуквенных токенов (цифры, знаки) - пропускаем

    # Подсчет уникальных лемм
    unique_lemmas = set(lemmas_list)
    unique_lemmas_count = len(unique_lemmas)

    # Формируем строку лемм (с повторениями для сохранения порядка)
    lemmatized_text = ' '.join(lemmas_list)

    return lemmatized_text, unique_lemmas_count, total_tokens


def insert_lemmatized(conn, doc_id, lemmatized_text, unique_lemmas_count, total_tokens):
    """Вставляет лемматизированный текст в таблицу"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id FROM documents_lemmatized WHERE id_documents = %s
        """, (doc_id,))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE documents_lemmatized 
                SET content = %s, 
                    unique_lemmas_count = %s, 
                    total_tokens_count = %s,
                    created_at = CURRENT_TIMESTAMP 
                WHERE id_documents = %s
            """, (lemmatized_text, unique_lemmas_count, total_tokens, doc_id))
        else:
            cur.execute("""
                INSERT INTO documents_lemmatized (id_documents, content, unique_lemmas_count, total_tokens_count)
                VALUES (%s, %s, %s, %s)
            """, (doc_id, lemmatized_text, unique_lemmas_count, total_tokens))

        conn.commit()


def main():
    print("Инициализация анализатора pymorphy3...")
    morph = MorphAnalyzer()

    print("Подключение к БД...")
    conn = connect_db()

    try:
        print("Создание/проверка таблицы...")
        create_lemmatized_table(conn)

        print("Загрузка документов...")
        documents = fetch_documents(conn)
        print(f"Найдено документов: {len(documents)}")

        processed_count = 0
        total_unique_lemmas = 0
        total_tokens = 0

        for doc_id, content in documents:
            if content:
                print(f"Обработка документа ID: {doc_id}")
                lemmatized_text, unique_lemmas_count, tokens_count = lemmatize_text(content, morph)
                insert_lemmatized(conn, doc_id, lemmatized_text, unique_lemmas_count, tokens_count)
                processed_count += 1
                total_unique_lemmas += unique_lemmas_count
                total_tokens += tokens_count

                print(f"  -> Уникальных лемм: {unique_lemmas_count}, Всего токенов: {tokens_count}")
                print(f"  -> Коэффициент разнообразия словаря: {unique_lemmas_count / tokens_count * 100:.2f}%")

                if processed_count % 10 == 0:
                    print(f"Обработано {processed_count} документов...")

        print(f"\nГотово! Обработано {processed_count} документов.")
        print(f"Всего уникальных лемм (суммарно по документам): {total_unique_lemmas}")
        print(f"Всего токенов: {total_tokens}")
        print(f"Среднее количество уникальных лемм на документ: {total_unique_lemmas / processed_count:.2f}")
        print(f"Среднее количество токенов на документ: {total_tokens / processed_count:.2f}")

        # Проверяем результат
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents_lemmatized")
            count = cur.fetchone()[0]
            print(f"В таблицу documents_lemmatized добавлено {count} записей")

            # Показываем статистику по таблице
            cur.execute("""
                SELECT 
                    COUNT(*) as total_docs,
                    SUM(unique_lemmas_count) as total_unique_lemmas,
                    SUM(total_tokens_count) as total_tokens,
                    AVG(unique_lemmas_count) as avg_unique_lemmas,
                    AVG(total_tokens_count) as avg_tokens,
                    AVG(unique_lemmas_count * 1.0 / NULLIF(total_tokens_count, 0)) * 100 as avg_vocabulary_diversity
                FROM documents_lemmatized
            """)
            stats = cur.fetchone()
            print(f"\nСтатистика по таблице documents_lemmatized:")
            print(f"  - Всего документов: {stats[0]}")
            print(f"  - Всего уникальных лемм (суммарно): {stats[1]}")
            print(f"  - Всего токенов: {stats[2]}")
            print(f"  - Среднее уникальных лемм на документ: {stats[3]:.2f}")
            print(f"  - Среднее токенов на документ: {stats[4]:.2f}")
            print(f"  - Средний коэффициент разнообразия словаря: {stats[5]:.2f}%")

            # Показываем пример для проверки
            print("\nПример обработки (для проверки):")
            cur.execute("""
                SELECT id_documents, content, unique_lemmas_count, total_tokens_count 
                FROM documents_lemmatized 
                WHERE content LIKE '%ижгту%' 
                LIMIT 1
            """)
            sample = cur.fetchone()
            if sample:
                print(f"Документ ID: {sample[0]}")
                print(f"Уникальных лемм: {sample[2]}, Всего токенов: {sample[3]}")
                diversity = sample[2] / sample[3] * 100 if sample[3] > 0 else 0
                print(f"Коэффициент разнообразия: {diversity:.2f}%")
                preview = sample[1][:300] if sample[1] else "пусто"
                print(f"Лемматизированный фрагмент: {preview}...")
            else:
                print("Документов с 'ижгту' не найдено")

    except Exception as e:
        print(f"Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()