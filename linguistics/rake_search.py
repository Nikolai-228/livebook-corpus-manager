import psycopg2
import re
from rake_nltk import Rake
from nltk.corpus import stopwords
import nltk

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


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


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


def search_rake_keywords(search_phrase: str, limit: int = 20):
    """Поиск ключевых слов и словосочетаний методом RAKE"""
    print(f"\n{'=' * 60}")
    print(f"🔍 ПОИСК ПО КЛЮЧЕВЫМ СЛОВАМ (RAKE): '{search_phrase}'")
    print(f"{'=' * 60}")

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, content 
                FROM documents 
                WHERE content IS NOT NULL AND content != ''
            """)
            documents = cur.fetchall()

        search_phrase_lower = search_phrase.lower().strip()
        results = []

        for doc_id, title, content in documents:
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
                start = max(0, found - 60)
                end = min(len(content), found + len(search_phrase) + 60)
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


def get_rake_keywords_for_document(doc_id: int, top_n: int = 20):
    """Извлекает ключевые слова RAKE для конкретного документа"""
    print(f"\n{'=' * 60}")
    print(f"🔑 КЛЮЧЕВЫЕ СЛОВА ДЛЯ ДОКУМЕНТА ID: {doc_id}")
    print(f"{'=' * 60}")

    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, content, type FROM documents WHERE id = %s", (doc_id,))
            result = cur.fetchone()
            if not result:
                print("❌ Документ не найден")
                return

            doc_id, title, content, doc_type = result
            print(f"\n📄 Информация о документе:")
            print(f"   ID: {doc_id}")
            print(f"   Название: {title[:150] if title else 'Без названия'}")
            print(f"   Тип файла: {doc_type if doc_type else 'Не указан'}")
            print(f"   Размер текста: {len(content)} символов")

            # Очищаем текст
            cleaned_text = re.sub(r'[^\w\s]', ' ', content.lower())

            # Создаем RAKE экстрактор
            rake = Rake(language='russian', stopwords=RUSSIAN_STOP_WORDS, min_length=2, max_length=4)
            rake.extract_keywords_from_text(cleaned_text)

            ranked_phrases = rake.get_ranked_phrases_with_scores()

            print(f"\n🏆 ТОП-{top_n} КЛЮЧЕВЫХ СЛОВ И СЛОВОСОЧЕТАНИЙ:")
            print(f"{'─' * 60}")

            valid_phrases = []
            for score, phrase in ranked_phrases:
                if len(phrase.split()) <= 4:
                    valid_phrases.append((score, phrase))

            for i, (score, phrase) in enumerate(valid_phrases[:top_n], 1):
                # Находим контекст для ключевой фразы
                contexts = []
                text_lower = content.lower()
                pos = 0
                while len(contexts) < 2:
                    found = text_lower.find(phrase, pos)
                    if found == -1:
                        break
                    start = max(0, found - 50)
                    end = min(len(content), found + len(phrase) + 50)
                    contexts.append(content[start:end].replace('\n', ' '))
                    pos = found + 1

                print(f"\n{i:2d}. \"{phrase}\"")
                print(f"    Релевантность: {score:.3f}")
                if contexts:
                    print(f"    Пример контекста: ...{contexts[0][:120]}...")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()


def interactive_rake_keywords():
    """Интерактивный режим для выбора документа и вывода ключевых слов"""
    print(f"\n{'=' * 60}")
    print("🔑 ИЗВЛЕЧЕНИЕ КЛЮЧЕВЫХ СЛОВ RAKE ПО ДОКУМЕНТУ")
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

    # Ввод количества ключевых слов
    while True:
        try:
            top_n = input("\n👉 Введите количество ключевых слов для вывода (по умолчанию 20): ").strip()
            if not top_n:
                top_n = 20
                break
            top_n = int(top_n)
            if 1 <= top_n <= 100:
                break
            else:
                print("❌ Пожалуйста, введите число от 1 до 100")
        except ValueError:
            print("❌ Пожалуйста, введите корректное число")

    # Выводим ключевые слова
    get_rake_keywords_for_document(doc_id, top_n)


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА RAKE (КЛЮЧЕВЫЕ СЛОВА И ФРАЗЫ)")
    print("=" * 60)
    print("\nВыберите действие:")
    print("1 - Поиск по ключевой фразе во всех документах")
    print("2 - Извлечение ключевых слов из конкретного документа")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        phrase = input("Введите ключевую фразу для поиска: ").strip()
        if phrase:
            search_rake_keywords(phrase)
        else:
            print("❌ Фраза не может быть пустой!")
    elif choice == '2':
        interactive_rake_keywords()
    else:
        print("❌ Неверный выбор! Запустите программу снова.")