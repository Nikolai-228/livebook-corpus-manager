import psycopg2
from nltk.tokenize import word_tokenize
from nltk.collocations import BigramCollocationFinder, TrigramCollocationFinder
from nltk.metrics import BigramAssocMeasures, TrigramAssocMeasures
from nltk.corpus import stopwords
from pymorphy3 import MorphAnalyzer
from rake_nltk import Rake
import nltk
import re
from collections import Counter
from typing import List, Dict, Optional, Tuple
from enum import Enum
import sys

# Скачиваем необходимые данные NLTK
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

# Русские стоп-слова
RUSSIAN_STOP_WORDS = set(stopwords.words('russian'))

# Защищенные слова (не лемматизируются)
PROTECTED_WORDS = {'ижгту'}


# Типы файлов
class FileType(Enum):
    ALL = "all"
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    GOOGLE_DOC = "google.doc"

    @classmethod
    def get_db_filter(cls, file_type: str):
        """Возвращает фильтр для SQL запроса"""
        if file_type == "all":
            return None
        return file_type


# Виды поиска
class SearchType(Enum):
    UNIGRAM = "unigram"  # Поиск по отдельным словам
    BIGRAM = "bigram"  # Поиск по биграммам
    TRIGRAM = "trigram"  # Поиск по триграммам
    RAKE = "rake"  # Поиск через RAKE
    COLLOCATIONS = "collocations"  # Поиск коллокаций (прил+сущ)
    TOP_TRIGRAMS = "top_trigrams"  # Топ триграммы по всем документам


def connect_db():
    """Подключение к базе данных"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        sys.exit(1)


def get_file_types_from_db() -> List[str]:
    """Получает все уникальные типы файлов из БД"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT type 
                FROM documents 
                WHERE type IS NOT NULL AND type != ''
                ORDER BY type
            """)
            types = [row[0] for row in cur.fetchall()]
            return types
    except Exception as e:
        print(f"⚠️ Ошибка получения типов файлов: {e}")
        return ['pdf', 'docx', 'doc', 'google.doc']
    finally:
        conn.close()


def preprocess_text(text: str, morph: MorphAnalyzer) -> List[str]:
    """Предобработка текста: токенизация и лемматизация"""
    if not text:
        return []

    # Очистка текста
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    tokens = word_tokenize(text, language='russian')
    tokens = [t for t in tokens if t.isalpha() and t not in RUSSIAN_STOP_WORDS]

    # Лемматизация
    lemmas = []
    for token in tokens:
        if token in PROTECTED_WORDS:
            lemmas.append(token)
            continue
        try:
            lemma = morph.parse(token)[0].normal_form
            if len(lemma) >= 2:
                lemmas.append(lemma)
        except Exception:
            continue

    return lemmas


def load_documents(file_type: str) -> List[Tuple]:
    """Загружает документы из БД с фильтром по типу файла"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            if file_type == "all":
                cur.execute("""
                    SELECT id, title, content, type 
                    FROM documents 
                    WHERE content IS NOT NULL AND content != ''
                """)
            else:
                cur.execute("""
                    SELECT id, title, content, type 
                    FROM documents 
                    WHERE content IS NOT NULL AND content != '' 
                    AND type = %s
                """, (file_type,))

            documents = cur.fetchall()
            print(f"📁 Загружено документов: {len(documents)} (тип: {file_type})")
            return documents
    finally:
        conn.close()


# ==================== ПОИСК ПО УНИГРАММАМ ====================
def search_unigrams(search_word: str, file_type: str, limit: int = 20) -> List[Dict]:
    """Поиск по униграммам (отдельным словам)"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ПО УНИГРАММАМ: '{search_word}' (Тип файла: {file_type})")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()
    documents = load_documents(file_type)

    # Получаем лемму искомого слова
    search_lemma = preprocess_text(search_word, morph)
    if not search_lemma:
        print("❌ Не удалось определить лемму для поиска")
        return []
    search_lemma = search_lemma[0]

    results = []
    for doc_id, title, content, doc_type in documents:
        if not content:
            continue

        lemmas = preprocess_text(content, morph)
        freq = lemmas.count(search_lemma)

        if freq > 0:
            # Находим контексты
            contexts = []
            text_lower = content.lower()
            pos = 0
            while len(contexts) < 3:
                found = text_lower.find(search_word.lower(), pos)
                if found == -1:
                    break
                start = max(0, found - 60)
                end = min(len(content), found + len(search_word) + 60)
                contexts.append(content[start:end].replace('\n', ' '))
                pos = found + 1

            results.append({
                'id': doc_id,
                'title': title[:150] if title else "Без названия",
                'type': doc_type,
                'frequency': freq,
                'contexts': contexts
            })

    results.sort(key=lambda x: x['frequency'], reverse=True)

    # Выводим результаты
    print(f"\n✅ Найдено документов: {len(results[:limit])}")
    for i, r in enumerate(results[:limit], 1):
        print(f"\n📄 [{i}] Документ ID: {r['id']}")
        print(f"   📝 Название: {r['title']}")
        print(f"   📎 Тип файла: {r['type']}")
        print(f"   🔥 Частота вхождения: {r['frequency']}")
        for j, ctx in enumerate(r['contexts'][:2], 1):
            ctx_clean = re.sub(r'\s+', ' ', ctx)
            print(f"   📖 Контекст {j}: ...{ctx_clean[:150]}...")

    return results[:limit]


# ==================== ПОИСК ПО БИГРАММАМ ====================
def search_bigrams(phrase: str, file_type: str, limit: int = 20) -> List[Dict]:
    """Поиск по биграммам с использованием NLTK"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ПО БИГРАММАМ: '{phrase}' (Тип файла: {file_type})")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()
    documents = load_documents(file_type)

    # Получаем леммы искомой фразы
    search_lemmas = preprocess_text(phrase, morph)
    if len(search_lemmas) < 2:
        print("❌ Не удалось определить леммы для поиска (нужно 2 слова)")
        return []
    search_bigram = ' '.join(search_lemmas[:2])

    results = []
    for doc_id, title, content, doc_type in documents:
        if not content:
            continue

        lemmas = preprocess_text(content, morph)

        # Находим биграммы
        finder = BigramCollocationFinder.from_words(lemmas)
        finder.apply_freq_filter(1)

        # Проверяем наличие искомой биграммы
        found = False
        freq = 0
        for bigram in finder.ngram_fd.items():
            bigram_text = ' '.join(bigram[0])
            if bigram_text == search_bigram:
                found = True
                freq = bigram[1]
                break

        if found:
            # Находим контексты
            contexts = []
            text_lower = content.lower()
            pos = 0
            while len(contexts) < 3:
                found_pos = text_lower.find(phrase.lower(), pos)
                if found_pos == -1:
                    break
                start = max(0, found_pos - 70)
                end = min(len(content), found_pos + len(phrase) + 70)
                contexts.append(content[start:end].replace('\n', ' '))
                pos = found_pos + 1

            results.append({
                'id': doc_id,
                'title': title[:150] if title else "Без названия",
                'type': doc_type,
                'frequency': freq,
                'contexts': contexts
            })

    results.sort(key=lambda x: x['frequency'], reverse=True)

    print(f"\n✅ Найдено документов: {len(results[:limit])}")
    for i, r in enumerate(results[:limit], 1):
        print(f"\n📄 [{i}] Документ ID: {r['id']}")
        print(f"   📝 Название: {r['title']}")
        print(f"   📎 Тип файла: {r['type']}")
        print(f"   🔥 Частота вхождения: {r['frequency']}")
        for j, ctx in enumerate(r['contexts'][:2], 1):
            ctx_clean = re.sub(r'\s+', ' ', ctx)
            print(f"   📖 Контекст {j}: ...{ctx_clean[:150]}...")

    return results[:limit]


# ==================== ПОИСК ПО ТРИГРАММАМ ====================
def search_trigrams(phrase: str, file_type: str, limit: int = 20) -> List[Dict]:
    """Поиск по триграммам с использованием NLTK"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ПО ТРИГРАММАМ: '{phrase}' (Тип файла: {file_type})")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()
    documents = load_documents(file_type)

    # Получаем леммы искомой фразы
    search_lemmas = preprocess_text(phrase, morph)
    if len(search_lemmas) < 3:
        print("❌ Не удалось определить леммы для поиска (нужно 3 слова)")
        return []
    search_trigram = ' '.join(search_lemmas[:3])

    results = []
    for doc_id, title, content, doc_type in documents:
        if not content:
            continue

        lemmas = preprocess_text(content, morph)

        # Находим триграммы
        finder = TrigramCollocationFinder.from_words(lemmas)
        finder.apply_freq_filter(1)

        # Проверяем наличие искомой триграммы
        found = False
        freq = 0
        for trigram in finder.ngram_fd.items():
            trigram_text = ' '.join(trigram[0])
            if trigram_text == search_trigram:
                found = True
                freq = trigram[1]
                break

        if found:
            # Находим контексты
            contexts = []
            text_lower = content.lower()
            pos = 0
            while len(contexts) < 3:
                found_pos = text_lower.find(phrase.lower(), pos)
                if found_pos == -1:
                    break
                start = max(0, found_pos - 80)
                end = min(len(content), found_pos + len(phrase) + 80)
                contexts.append(content[start:end].replace('\n', ' '))
                pos = found_pos + 1

            results.append({
                'id': doc_id,
                'title': title[:150] if title else "Без названия",
                'type': doc_type,
                'frequency': freq,
                'contexts': contexts
            })

    results.sort(key=lambda x: x['frequency'], reverse=True)

    print(f"\n✅ Найдено документов: {len(results[:limit])}")
    for i, r in enumerate(results[:limit], 1):
        print(f"\n📄 [{i}] Документ ID: {r['id']}")
        print(f"   📝 Название: {r['title']}")
        print(f"   📎 Тип файла: {r['type']}")
        print(f"   🔥 Частота вхождения: {r['frequency']}")
        for j, ctx in enumerate(r['contexts'][:2], 1):
            ctx_clean = re.sub(r'\s+', ' ', ctx)
            print(f"   📖 Контекст {j}: ...{ctx_clean[:150]}...")

    return results[:limit]


# ==================== ПОИСК ЧЕРЕЗ RAKE ====================
def search_rake(phrase: str, file_type: str, limit: int = 20) -> List[Dict]:
    """Поиск через RAKE (ключевые слова и фразы)"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ПО RAKE: '{phrase}' (Тип файла: {file_type})")
    print(f"{'=' * 70}")

    documents = load_documents(file_type)
    search_phrase_lower = phrase.lower().strip()

    results = []
    for doc_id, title, content, doc_type in documents:
        if not content:
            continue

        # Очищаем текст
        cleaned_text = re.sub(r'[^\w\s]', ' ', content.lower())

        # Проверяем наличие фразы
        if search_phrase_lower not in cleaned_text:
            continue

        # Подсчет частоты
        freq = cleaned_text.count(search_phrase_lower)

        # Находим контексты
        contexts = []
        pos = 0
        text_lower = content.lower()
        while len(contexts) < 3:
            found = text_lower.find(search_phrase_lower, pos)
            if found == -1:
                break
            start = max(0, found - 70)
            end = min(len(content), found + len(phrase) + 70)
            contexts.append(content[start:end].replace('\n', ' '))
            pos = found + 1

        results.append({
            'id': doc_id,
            'title': title[:150] if title else "Без названия",
            'type': doc_type,
            'frequency': freq,
            'contexts': contexts
        })

    results.sort(key=lambda x: x['frequency'], reverse=True)

    print(f"\n✅ Найдено документов: {len(results[:limit])}")
    for i, r in enumerate(results[:limit], 1):
        print(f"\n📄 [{i}] Документ ID: {r['id']}")
        print(f"   📝 Название: {r['title']}")
        print(f"   📎 Тип файла: {r['type']}")
        print(f"   🔥 Частота вхождения: {r['frequency']}")
        for j, ctx in enumerate(r['contexts'][:2], 1):
            ctx_clean = re.sub(r'\s+', ' ', ctx)
            print(f"   📖 Контекст {j}: ...{ctx_clean[:150]}...")

    return results[:limit]


# ==================== КОЛЛОКАЦИИ ====================
def get_collocations(file_type: str, limit: int = 30) -> List[Dict]:
    """Извлечение коллокаций (прилагательное + существительное)"""
    print(f"\n{'=' * 70}")
    print(f"🔍 КОЛЛОКАЦИИ (прилагательное + существительное) - Тип файла: {file_type}")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()
    documents = load_documents(file_type)

    # Собираем все леммы из всех документов
    all_lemmas = []
    for _, _, content, _ in documents:
        if content:
            lemmas = preprocess_text(content, morph)
            all_lemmas.extend(lemmas)

    # Находим биграммы
    finder = BigramCollocationFinder.from_words(all_lemmas)
    finder.apply_freq_filter(2)

    # Фильтруем коллокации (прилагательное + существительное)
    collocations = []
    for bigram, freq in finder.ngram_fd.items():
        word1 = bigram[0]
        word2 = bigram[1]
        try:
            pos1 = morph.parse(word1)[0].tag.POS
            pos2 = morph.parse(word2)[0].tag.POS
            if pos1 == 'ADJF' and pos2 == 'NOUN':
                collocations.append({
                    'phrase': f"{word1} {word2}",
                    'frequency': freq,
                    'word1': word1,
                    'word2': word2,
                    'pos1': pos1,
                    'pos2': pos2
                })
        except Exception:
            continue

    collocations.sort(key=lambda x: x['frequency'], reverse=True)

    print(f"\n🏆 ТОП-{limit} КОЛЛОКАЦИЙ:")
    for i, colloc in enumerate(collocations[:limit], 1):
        print(f"   {i}. \"{colloc['phrase']}\" (частота: {colloc['frequency']})")

    return collocations[:limit]


# ==================== ТОП ТРИГРАММЫ ====================
def get_top_trigrams(file_type: str, limit: int = 20) -> List[Dict]:
    """Извлечение наиболее частотных триграмм из всех документов"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ТОП ТРИГРАММЫ - Тип файла: {file_type}")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()
    documents = load_documents(file_type)

    # Собираем все леммы из всех документов
    all_lemmas = []
    for _, _, content, _ in documents:
        if content:
            lemmas = preprocess_text(content, morph)
            all_lemmas.extend(lemmas)

    # Находим триграммы
    finder = TrigramCollocationFinder.from_words(all_lemmas)
    finder.apply_freq_filter(2)

    trigrams = []
    for trigram, freq in finder.ngram_fd.items():
        trigrams.append({
            'phrase': ' '.join(trigram),
            'frequency': freq,
            'words': list(trigram)
        })

    trigrams.sort(key=lambda x: x['frequency'], reverse=True)

    print(f"\n🏆 ТОП-{limit} ТРИГРАММ:")
    for i, trigram in enumerate(trigrams[:limit], 1):
        print(f"   {i}. \"{trigram['phrase']}\" (частота: {trigram['frequency']})")

    return trigrams[:limit]


# ==================== ОСНОВНАЯ ФУНКЦИЯ МАСКИ ПОИСКА ====================
def search_mask(
        search_type: str,
        query: Optional[str] = None,
        file_type: str = "all",
        limit: int = 20
) -> List[Dict]:
    """
    Унифицированная маска поиска

    Параметры:
    - search_type: тип поиска (unigram, bigram, trigram, rake, collocations, top_trigrams)
    - query: поисковый запрос (для collocations и top_trigrams не нужен)
    - file_type: тип файла (all, pdf, docx, doc, google.doc)
    - limit: лимит результатов

    Возвращает:
    - Список результатов поиска
    """

    # Проверяем валидность типа поиска
    try:
        search_enum = SearchType(search_type)
    except ValueError:
        print(f"❌ Неизвестный тип поиска: {search_type}")
        print(f"   Доступные типы: {[t.value for t in SearchType]}")
        return []

    # Для collocations и top_trigrams query не требуется
    if search_enum in [SearchType.COLLOCATIONS, SearchType.TOP_TRIGRAMS]:
        if search_enum == SearchType.COLLOCATIONS:
            return get_collocations(file_type, limit)
        else:
            return get_top_trigrams(file_type, limit)

    # Для остальных типов проверяем наличие query
    if not query:
        print("❌ Для этого типа поиска требуется поисковый запрос (query)")
        return []

    # Выполняем соответствующий поиск
    if search_enum == SearchType.UNIGRAM:
        return search_unigrams(query, file_type, limit)
    elif search_enum == SearchType.BIGRAM:
        return search_bigrams(query, file_type, limit)
    elif search_enum == SearchType.TRIGRAM:
        return search_trigrams(query, file_type, limit)
    elif search_enum == SearchType.RAKE:
        return search_rake(query, file_type, limit)
    else:
        print(f"❌ Неподдерживаемый тип поиска: {search_type}")
        return []


# ==================== ИНТЕРАКТИВНОЕ МЕНЮ ====================
def interactive_menu():
    """Интерактивное меню для выбора параметров поиска"""
    print("\n" + "=" * 70)
    print("🔍 МАСКА ПОИСКА N-ГРАММ И КОЛЛОКАЦИЙ")
    print("=" * 70)

    # Получаем доступные типы файлов из БД
    available_types = get_file_types_from_db()

    # Выводим информацию о БД
    print(f"\n💾 База данных: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"📁 Доступные типы файлов в БД: {', '.join(available_types)}")

    # Выбор типа поиска
    print("\n📋 ВИДЫ ПОИСКА:")
    print("   1. Поиск по униграммам (отдельные слова)")
    print("   2. Поиск по биграммам (2 слова)")
    print("   3. Поиск по триграммам (3 слова)")
    print("   4. Поиск через RAKE (ключевые фразы)")
    print("   5. Извлечение коллокаций (прилагательное + существительное)")
    print("   6. Извлечение топ-триграмм из всех документов")

    search_choice = input("\n👉 Выберите вид поиска (1-6): ").strip()

    search_type_map = {
        '1': 'unigram',
        '2': 'bigram',
        '3': 'trigram',
        '4': 'rake',
        '5': 'collocations',
        '6': 'top_trigrams'
    }

    if search_choice not in search_type_map:
        print("❌ Неверный выбор!")
        return

    search_type = search_type_map[search_choice]

    # Выбор типа файла
    print("\n📎 ТИПЫ ФАЙЛОВ:")
    print("   0. Все типы файлов")
    for i, file_type in enumerate(available_types, 1):
        print(f"   {i}. {file_type}")

    type_choice = input("\n👉 Выберите тип файла (0-{}): ".format(len(available_types))).strip()

    if type_choice == '0':
        file_type = "all"
    else:
        try:
            idx = int(type_choice) - 1
            if 0 <= idx < len(available_types):
                file_type = available_types[idx]
            else:
                print("❌ Неверный выбор! Использую 'all'")
                file_type = "all"
        except:
            print("❌ Неверный выбор! Использую 'all'")
            file_type = "all"

    # Ввод поискового запроса (если нужно)
    query = None
    if search_type in ['unigram', 'bigram', 'trigram', 'rake']:
        query = input("\n🔎 Введите поисковый запрос: ").strip()
        if not query:
            print("❌ Поисковый запрос не может быть пустым!")
            return

    # Ввод лимита
    try:
        limit_input = input("\n📊 Максимальное количество результатов (по умолчанию 20): ").strip()
        limit = int(limit_input) if limit_input else 20
    except:
        limit = 20

    # Выполняем поиск
    print("\n" + "🔄 ВЫПОЛНЕНИЕ ПОИСКА...")
    results = search_mask(search_type, query, file_type, limit)

    # Сохраняем результаты в JSON формате для дальнейшего использования на сайте
    if results:
        import json
        output_file = f"search_results_{search_type}_{file_type}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            # Преобразуем результаты в JSON-совместимый формат
            json_results = []
            for r in results:
                json_r = r.copy()
                # Обрабатываем контексты для JSON
                if 'contexts' in json_r:
                    json_r['contexts'] = [ctx.strip() for ctx in json_r['contexts']]
                json_results.append(json_r)

            json.dump(json_results, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Результаты сохранены в файл: {output_file}")

    print("\n✅ Поиск завершен!")


# ==================== ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ====================
def examples():
    """Примеры использования маски поиска"""
    print("\n" + "=" * 70)
    print("📚 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ МАСКИ ПОИСКА")
    print("=" * 70)

    # Пример 1: Поиск униграмм в PDF файлах
    print("\n1️⃣ Поиск униграмм 'Ижевск' в PDF документах:")
    results1 = search_mask('unigram', 'Ижевск', 'pdf', limit=5)

    # Пример 2: Поиск биграмм во всех файлах
    print("\n2️⃣ Поиск биграммы 'искусственный интеллект' во всех файлах:")
    results2 = search_mask('bigram', 'искусственный интеллект', 'all', limit=5)

    # Пример 3: Извлечение коллокаций из DOCX файлов
    print("\n3️⃣ Извлечение коллокаций из DOCX документов:")
    results3 = search_mask('collocations', file_type='docx', limit=10)

    # Пример 4: Топ триграммы из Google Docs
    print("\n4️⃣ Топ триграммы из Google Docs:")
    results4 = search_mask('top_trigrams', file_type='google.doc', limit=10)


# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    print("🔍 УНИФИЦИРОВАННАЯ МАСКА ПОИСКА N-ГРАММ И КОЛЛОКАЦИЙ")
    print("=" * 70)

    while True:
        print("\n📋 МЕНЮ:")
        print("   1. Интерактивный режим (выбор параметров)")
        print("   2. Запустить примеры")
        print("   3. Выйти")

        choice = input("\n👉 Ваш выбор (1-3): ").strip()

        if choice == '1':
            interactive_menu()
        elif choice == '2':
            examples()
        elif choice == '3':
            print("\n👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор!")