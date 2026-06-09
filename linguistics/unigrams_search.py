import psycopg2
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from pymorphy3 import MorphAnalyzer
import nltk
import re
from collections import Counter

# Скачиваем необходимые данные
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('stopwords', quiet=True)

DB_CONFIG = {
    'host': 'livebook-team.duckdns.org',
    'port': 5432,
    'user': 'team_user',
    'password': 'book_live',
    'database': 'livebook_corpus'
}

RUSSIAN_STOP_WORDS = set(stopwords.words('russian'))

ABBREVIATIONS = {
    'ИжГТУ': 'ижгту', 'ижгту': 'ижгту', 'ими': 'ими',
}

PROTECTED_WORDS = {'ижгту'}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def lemmatize_text(text: str, morph) -> list:
    """Лемматизация текста"""
    if not text:
        return []

    # Очистка текста
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = word_tokenize(text.lower(), language='russian')
    tokens = [t for t in tokens if t.isalpha() and t not in RUSSIAN_STOP_WORDS]

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
            pass

    return lemmas


def get_all_documents():
    """Получает список всех документов из БД"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, type 
                FROM documents 
                WHERE content IS NOT NULL AND content != ''
                ORDER BY id
            """)
            documents = cur.fetchall()
        return documents
    except Exception as e:
        print(f"Ошибка при получении списка документов: {e}")
        return []
    finally:
        conn.close()


def search_unigrams(search_word: str, limit: int = 20):
    """Поиск по униграммам (отдельным словам)"""
    print(f"\n{'=' * 60}")
    print(f"🔍 ПОИСК ПО УНИГРАММАМ: '{search_word}'")
    print(f"{'=' * 60}")

    morph = MorphAnalyzer()
    conn = connect_db()

    try:
        # Получаем лемму искомого слова
        search_lemma = lemmatize_text(search_word, morph)
        if not search_lemma:
            print("Не удалось определить лемму для поиска")
            return
        search_lemma = search_lemma[0]

        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, content 
                FROM documents 
                WHERE content IS NOT NULL AND content != ''
            """)
            documents = cur.fetchall()

        results = []
        for doc_id, title, content in documents:
            if not content:
                continue

            lemmas = lemmatize_text(content, morph)
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
                    start = max(0, found - 50)
                    end = min(len(content), found + len(search_word) + 50)
                    contexts.append(content[start:end].replace('\n', ' '))
                    pos = found + 1

                results.append({
                    'id': doc_id,
                    'title': title[:100] if title else "Без названия",
                    'frequency': freq,
                    'contexts': contexts
                })

        results.sort(key=lambda x: x['frequency'], reverse=True)

        print(f"\nНайдено документов: {len(results[:limit])}")
        for r in results[:limit]:
            print(f"\n📄 Документ ID: {r['id']}")
            print(f"   Название: {r['title']}")
            print(f"   Частота вхождения: {r['frequency']}")
            for i, ctx in enumerate(r['contexts'][:2]):
                ctx_clean = re.sub(r'\s+', ' ', ctx)
                print(f"   Контекст {i + 1}: ...{ctx_clean[:150]}...")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()


def get_top_unigrams_in_document(doc_id: int, top_n: int = 20):
    """Выводит топ-N самых часто встречаемых униграмм в конкретном документе"""
    print(f"\n{'=' * 60}")
    print(f"📊 ТОП-{top_n} УНИГРАММ В ДОКУМЕНТЕ ID: {doc_id}")
    print(f"{'=' * 60}")

    morph = MorphAnalyzer()
    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, content, type 
                FROM documents 
                WHERE id = %s AND content IS NOT NULL AND content != ''
            """, (doc_id,))
            document = cur.fetchone()

            if not document:
                print(f"❌ Документ с ID {doc_id} не найден или не содержит текста")
                return

            doc_id, title, content, doc_type = document

            print(f"\n📄 Информация о документе:")
            print(f"   ID: {doc_id}")
            print(f"   Название: {title[:150] if title else 'Без названия'}")
            print(f"   Тип файла: {doc_type if doc_type else 'Не указан'}")
            print(f"   Размер текста: {len(content)} символов")

            # Лемматизируем текст
            print(f"\n🔄 Выполняется лемматизация текста...")
            lemmas = lemmatize_text(content, morph)
            print(f"   Получено лемм: {len(lemmas)}")

            # Подсчитываем частоту каждой леммы
            lemma_freq = Counter(lemmas)

            # Получаем топ-N лемм
            top_lemmas = lemma_freq.most_common(top_n)

            print(f"\n📊 ТОП-{top_n} САМЫХ ЧАСТЫХ УНИГРАММ (ЛЕММ):")
            print(f"{'─' * 60}")

            for i, (lemma, freq) in enumerate(top_lemmas, 1):
                # Находим контекст для каждой топ-леммы
                contexts = []
                text_lower = content.lower()
                pos = 0
                while len(contexts) < 2:  # Показываем 2 контекста для каждой леммы
                    # Ищем оригинальное слово (не лемму) в тексте
                    found = text_lower.find(lemma, pos)
                    if found == -1:
                        break
                    start = max(0, found - 40)
                    end = min(len(content), found + len(lemma) + 40)
                    contexts.append(content[start:end].replace('\n', ' '))
                    pos = found + 1

                print(f"\n{i:2d}. Слово: \"{lemma}\"")
                print(f"    Частота: {freq} раз(а)")
                if contexts:
                    print(f"    Пример контекста: ...{contexts[0][:100]}...")

            # Дополнительная статистика
            print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
            print(f"   Всего уникальных слов: {len(lemma_freq)}")
            print(f"   Всего слов (с повторениями): {len(lemmas)}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()


def show_documents_list():
    """Показывает список всех документов для выбора"""
    documents = get_all_documents()

    if not documents:
        print("❌ Нет доступных документов")
        return None

    print(f"\n{'=' * 60}")
    print("📚 СПИСОК ДОСТУПНЫХ ДОКУМЕНТОВ")
    print(f"{'=' * 60}")
    print(f"\n{'ID':<6} {'Тип':<12} {'Название'}")
    print(f"{'─' * 60}")

    for doc_id, title, doc_type in documents:
        title_short = title[:50] if title else "Без названия"
        doc_type_short = doc_type[:10] if doc_type else "Не указан"
        print(f"{doc_id:<6} {doc_type_short:<12} {title_short}")

    return documents


def interactive_top_unigrams():
    """Интерактивный режим для выбора документа и вывода топ униграмм"""
    print(f"\n{'=' * 60}")
    print("🏆 ВЫВОД ТОП-20 УНИГРАММ ПО ДОКУМЕНТУ")
    print(f"{'=' * 60}")

    # Показываем список документов
    documents = show_documents_list()

    if not documents:
        return

    # Выбор документа
    while True:
        try:
            doc_id = input(f"\n👉 Введите ID документа: ").strip()
            doc_id = int(doc_id)

            # Проверяем существует ли документ
            doc_exists = any(doc[0] == doc_id for doc in documents)
            if doc_exists:
                break
            else:
                print(f"❌ Документ с ID {doc_id} не найден. Попробуйте снова.")
        except ValueError:
            print("❌ Пожалуйста, введите корректный числовой ID")
        except KeyboardInterrupt:
            print("\n👋 Отмена")
            return

    # Выводим топ-20 униграмм
    get_top_unigrams_in_document(doc_id, 20)


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА УНИГРАММ")
    print("=" * 60)
    print("\nВыберите режим работы:")
    print("1 - Поиск по конкретному слову во всех документах")
    print("2 - Вывести топ-20 униграмм по конкретному документу")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        search_word = input("Введите слово для поиска: ").strip()
        if search_word:
            search_unigrams(search_word)
        else:
            print("❌ Слово не может быть пустым!")

    elif choice == '2':
        interactive_top_unigrams()

    else:
        print("❌ Неверный выбор! Запустите программу снова.")