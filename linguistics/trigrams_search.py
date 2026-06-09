import psycopg2
from nltk.tokenize import word_tokenize
from nltk.collocations import TrigramCollocationFinder
from nltk.metrics import TrigramAssocMeasures
from nltk.corpus import stopwords
from pymorphy3 import MorphAnalyzer
import nltk
import re

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

PROTECTED_WORDS = {'ижгту'}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def preprocess_text(text: str, morph) -> list:
    """Предобработка текста: токенизация и лемматизация"""
    if not text:
        return []

    text = re.sub(r'[^\w\s]', ' ', text.lower())
    tokens = word_tokenize(text, language='russian')
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


def search_trigrams(phrase: str, limit: int = 20):
    """Поиск по триграммам с использованием NLTK"""
    print(f"\n{'=' * 60}")
    print(f"🔍 ПОИСК ПО ТРИГРАММАМ: '{phrase}'")
    print(f"{'=' * 60}")

    morph = MorphAnalyzer()
    conn = connect_db()

    try:
        # Получаем леммы искомой фразы
        search_lemmas = preprocess_text(phrase, morph)
        if len(search_lemmas) < 3:
            print("Не удалось определить леммы для поиска (нужно 3 слова)")
            return
        search_trigram = ' '.join(search_lemmas[:3])

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

            lemmas = preprocess_text(content, morph)

            # Находим триграммы
            finder = TrigramCollocationFinder.from_words(lemmas)
            finder.apply_freq_filter(1)

            # Проверяем наличие искомой триграммы
            found = False
            freq = 0
            for trigram, score in finder.score_ngrams(TrigramAssocMeasures().pmi):
                trigram_text = ' '.join(trigram)
                if trigram_text == search_trigram:
                    found = True
                    freq = finder.ngram_fd[trigram]
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


def get_top_trigrams_all_documents(limit: int = 20):
    """Извлечение наиболее частотных триграмм из всех документов"""
    print(f"\n{'=' * 60}")
    print(f"🔍 ТОП-{limit} ТРИГРАММ ПО ВСЕМ ДОКУМЕНТАМ")
    print(f"{'=' * 60}")

    morph = MorphAnalyzer()
    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT content 
                FROM documents 
                WHERE content IS NOT NULL AND content != ''
            """)
            documents = cur.fetchall()

        # Собираем все леммы из всех документов
        all_lemmas = []
        for (content,) in documents:
            if content:
                lemmas = preprocess_text(content, morph)
                all_lemmas.extend(lemmas)

        # Находим триграммы
        finder = TrigramCollocationFinder.from_words(all_lemmas)
        finder.apply_freq_filter(2)

        trigrams = []
        for trigram, freq in finder.ngram_fd.items():
            trigrams.append((' '.join(trigram), freq))

        trigrams.sort(key=lambda x: x[1], reverse=True)

        print(f"\n🏆 ТОП-{limit} ТРИГРАММ:")
        for i, (trigram, freq) in enumerate(trigrams[:limit], 1):
            print(f"   {i}. \"{trigram}\" (частота: {freq})")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()


def get_top_trigrams_in_document(doc_id: int, top_n: int = 20):
    """Выводит топ-N самых часто встречаемых триграмм в конкретном документе"""
    print(f"\n{'=' * 60}")
    print(f"📊 ТОП-{top_n} ТРИГРАММ В ДОКУМЕНТЕ ID: {doc_id}")
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
            print(f"\n🔄 Выполняется обработка текста...")
            lemmas = preprocess_text(content, morph)
            print(f"   Получено лемм: {len(lemmas)}")

            # Находим триграммы
            finder = TrigramCollocationFinder.from_words(lemmas)
            finder.apply_freq_filter(1)

            # Получаем все триграммы с частотами
            trigrams_with_freq = []
            for trigram, freq in finder.ngram_fd.items():
                trigram_text = ' '.join(trigram)
                # Фильтруем слишком короткие или служебные триграммы
                if len(trigram_text) > 5:
                    trigrams_with_freq.append((trigram_text, freq))

            # Сортируем по частоте
            trigrams_with_freq.sort(key=lambda x: x[1], reverse=True)

            # Берем топ-N
            top_trigrams = trigrams_with_freq[:top_n]

            if not top_trigrams:
                print(f"\n⚠️ В документе не найдено триграмм")
                return

            print(f"\n📊 ТОП-{top_n} САМЫХ ЧАСТЫХ ТРИГРАММ:")
            print(f"{'─' * 60}")

            for i, (trigram, freq) in enumerate(top_trigrams, 1):
                # Находим контекст для каждой топ-триграммы
                contexts = []
                text_lower = content.lower()
                pos = 0
                while len(contexts) < 2:
                    found = text_lower.find(trigram, pos)
                    if found == -1:
                        break
                    start = max(0, found - 60)
                    end = min(len(content), found + len(trigram) + 60)
                    contexts.append(content[start:end].replace('\n', ' '))
                    pos = found + 1

                print(f"\n{i:2d}. Триграмма: \"{trigram}\"")
                print(f"    Частота: {freq} раз(а)")
                if contexts:
                    print(f"    Пример контекста: ...{contexts[0][:120]}...")

            # Дополнительная статистика
            print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
            print(f"   Всего уникальных триграмм: {len(trigrams_with_freq)}")
            print(f"   Всего триграмм (с повторениями): {sum(freq for _, freq in trigrams_with_freq)}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()


def interactive_top_trigrams():
    """Интерактивный режим для выбора: все документы или конкретный"""
    print(f"\n{'=' * 60}")
    print("🔍 ИЗВЛЕЧЕНИЕ ТОП ТРИГРАММ")
    print(f"{'=' * 60}")

    print("\nВыберите режим:")
    print("1 - По всем документам")
    print("2 - По конкретному документу")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        # Ввод количества триграмм для вывода
        try:
            top_n = input("\n👉 Введите количество триграмм для вывода (по умолчанию 20): ").strip()
            if not top_n:
                top_n = 20
            else:
                top_n = int(top_n)
            get_top_trigrams_all_documents(top_n)
        except ValueError:
            print("❌ Пожалуйста, введите корректное число")
            get_top_trigrams_all_documents(20)

    elif choice == '2':
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

        # Ввод количества триграмм для вывода
        try:
            top_n = input("\n👉 Введите количество триграмм для вывода (по умолчанию 20): ").strip()
            if not top_n:
                top_n = 20
            else:
                top_n = int(top_n)
                if top_n < 1 or top_n > 100:
                    print("❌ Пожалуйста, введите число от 1 до 100. Использую 20")
                    top_n = 20
        except ValueError:
            print("❌ Пожалуйста, введите корректное число. Использую 20")
            top_n = 20

        get_top_trigrams_in_document(doc_id, top_n)
    else:
        print("❌ Неверный выбор!")


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА ТРИГРАММ")
    print("=" * 60)
    print("\nВыберите действие:")
    print("1 - Поиск по триграмме во всех документах")
    print("2 - Извлечение топ триграмм (по всем документам или конкретному)")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        phrase = input("Введите фразу из 3 слов для поиска: ").strip()
        if phrase:
            search_trigrams(phrase)
        else:
            print("❌ Фраза не может быть пустой!")
    elif choice == '2':
        interactive_top_trigrams()
    else:
        print("❌ Неверный выбор! Запустите программу снова.")