import psycopg2
from nltk.tokenize import word_tokenize
from nltk.collocations import BigramCollocationFinder
from nltk.metrics import BigramAssocMeasures
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

PROTECTED_WORDS = {'ижгту'}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def preprocess_text(text: str, morph) -> tuple:
    """Предобработка текста: токенизация и лемматизация"""
    if not text:
        return [], []

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
            pass

    return tokens, lemmas


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


def search_bigrams(phrase: str, limit: int = 20):
    """Поиск по биграммам с использованием NLTK"""
    print(f"\n{'=' * 60}")
    print(f"🔍 ПОИСК ПО БИГРАММАМ: '{phrase}'")
    print(f"{'=' * 60}")

    morph = MorphAnalyzer()
    conn = connect_db()

    try:
        # Получаем леммы искомой фразы
        _, search_lemmas = preprocess_text(phrase, morph)
        if len(search_lemmas) < 2:
            print("Не удалось определить леммы для поиска (нужно 2 слова)")
            return
        search_bigram = ' '.join(search_lemmas[:2])

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

            _, lemmas = preprocess_text(content, morph)

            # Находим биграммы
            finder = BigramCollocationFinder.from_words(lemmas)
            finder.apply_freq_filter(1)

            # Проверяем наличие искомой биграммы
            found = False
            freq = 0
            for bigram, score in finder.score_ngrams(BigramAssocMeasures().pmi):
                bigram_text = ' '.join(bigram)
                if bigram_text == search_bigram:
                    found = True
                    freq = finder.ngram_fd[bigram]
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
                    start = max(0, found_pos - 60)
                    end = min(len(content), found_pos + len(phrase) + 60)
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


def get_top_bigrams_in_document(doc_id: int, top_n: int = 20):
    """Выводит топ-N самых часто встречаемых биграмм в конкретном документе"""
    print(f"\n{'=' * 60}")
    print(f"📊 ТОП-{top_n} БИГРАММ В ДОКУМЕНТЕ ID: {doc_id}")
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
            _, lemmas = preprocess_text(content, morph)
            print(f"   Получено лемм: {len(lemmas)}")

            # Находим биграммы
            finder = BigramCollocationFinder.from_words(lemmas)
            finder.apply_freq_filter(1)

            # Получаем все биграммы с частотами
            bigrams_with_freq = []
            for bigram, freq in finder.ngram_fd.items():
                bigram_text = ' '.join(bigram)
                # Фильтруем слишком короткие или служебные биграммы
                if len(bigram_text) > 3:
                    bigrams_with_freq.append((bigram_text, freq))

            # Сортируем по частоте
            bigrams_with_freq.sort(key=lambda x: x[1], reverse=True)

            # Берем топ-N
            top_bigrams = bigrams_with_freq[:top_n]

            print(f"\n📊 ТОП-{top_n} САМЫХ ЧАСТЫХ БИГРАММ:")
            print(f"{'─' * 60}")

            for i, (bigram, freq) in enumerate(top_bigrams, 1):
                # Находим контекст для каждой топ-биграммы
                contexts = []
                text_lower = content.lower()
                pos = 0
                while len(contexts) < 2:
                    found = text_lower.find(bigram, pos)
                    if found == -1:
                        break
                    start = max(0, found - 50)
                    end = min(len(content), found + len(bigram) + 50)
                    contexts.append(content[start:end].replace('\n', ' '))
                    pos = found + 1

                print(f"\n{i:2d}. Биграмма: \"{bigram}\"")
                print(f"    Частота: {freq} раз(а)")
                if contexts:
                    print(f"    Пример контекста: ...{contexts[0][:120]}...")

            # Дополнительная статистика
            print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
            print(f"   Всего уникальных биграмм: {len(bigrams_with_freq)}")
            print(f"   Всего биграмм (с повторениями): {sum(freq for _, freq in bigrams_with_freq)}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()


def get_collocations_in_document(doc_id: int, limit: int = 20):
    """Извлечение коллокаций (прилагательное + существительное) из конкретного документа"""
    print(f"\n{'=' * 60}")
    print(f"🔍 КОЛЛОКАЦИИ (прилагательное + существительное) В ДОКУМЕНТЕ ID: {doc_id}")
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
            _, lemmas = preprocess_text(content, morph)
            print(f"   Получено лемм: {len(lemmas)}")

            # Находим биграммы
            finder = BigramCollocationFinder.from_words(lemmas)
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
                        # Находим контекст для коллокации
                        contexts = []
                        text_lower = content.lower()
                        pos = 0
                        bigram_text = f"{word1} {word2}"
                        while len(contexts) < 2:
                            found = text_lower.find(bigram_text, pos)
                            if found == -1:
                                break
                            start = max(0, found - 50)
                            end = min(len(content), found + len(bigram_text) + 50)
                            contexts.append(content[start:end].replace('\n', ' '))
                            pos = found + 1

                        collocations.append({
                            'phrase': bigram_text,
                            'frequency': freq,
                            'contexts': contexts,
                            'word1': word1,
                            'word2': word2
                        })
                except Exception:
                    continue

            collocations.sort(key=lambda x: x['frequency'], reverse=True)

            if not collocations:
                print(f"\n⚠️ В документе не найдено коллокаций (прилагательное + существительное)")
                return

            print(f"\n🏆 ТОП-{limit} КОЛЛОКАЦИЙ (прилагательное + существительное):")
            print(f"{'─' * 60}")

            for i, colloc in enumerate(collocations[:limit], 1):
                print(f"\n{i:2d}. \"{colloc['phrase']}\"")
                print(f"    Частота: {colloc['frequency']} раз(а)")
                if colloc['contexts']:
                    print(f"    Пример контекста: ...{colloc['contexts'][0][:120]}...")

            # Дополнительная статистика
            print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
            print(f"   Всего найдено коллокаций: {len(collocations)}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()


def get_collocations_all_documents(limit: int = 20):
    """Извлечение коллокаций (прилагательное + существительное) из всех документов"""
    print(f"\n{'=' * 60}")
    print(f"🔍 ПОИСК КОЛЛОКАЦИЙ (прилагательное + существительное) ВО ВСЕХ ДОКУМЕНТАХ")
    print(f"{'=' * 60}")

    morph = MorphAnalyzer()
    conn = connect_db()

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, content 
                FROM documents 
                WHERE content IS NOT NULL AND content != ''
            """)
            documents = cur.fetchall()

        # Собираем все леммы из всех документов
        all_lemmas = []
        for _, content in documents:
            if content:
                _, lemmas = preprocess_text(content, morph)
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
                    collocations.append((f"{word1} {word2}", freq))
            except Exception:
                continue

        collocations.sort(key=lambda x: x[1], reverse=True)

        print(f"\n🏆 ТОП-{limit} КОЛЛОКАЦИЙ (прилагательное + существительное):")
        for i, (colloc, freq) in enumerate(collocations[:limit], 1):
            print(f"   {i}. \"{colloc}\" (частота: {freq})")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()


def interactive_top_bigrams():
    """Интерактивный режим для выбора документа и вывода топ биграмм"""
    print(f"\n{'=' * 60}")
    print("🏆 ВЫВОД ТОП-20 БИГРАММ ПО ДОКУМЕНТУ")
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

    # Выводим топ-20 биграмм
    get_top_bigrams_in_document(doc_id, 20)


def interactive_collocations():
    """Интерактивный режим для выбора: все документы или конкретный"""
    print(f"\n{'=' * 60}")
    print("🔍 ИЗВЛЕЧЕНИЕ КОЛЛОКАЦИЙ (прилагательное + существительное)")
    print(f"{'=' * 60}")

    print("\nВыберите режим:")
    print("1 - По всем документам")
    print("2 - По конкретному документу")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        get_collocations_all_documents(20)
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

        get_collocations_in_document(doc_id, 20)
    else:
        print("❌ Неверный выбор!")


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА БИГРАММ И КОЛЛОКАЦИЙ")
    print("=" * 60)
    print("\nВыберите действие:")
    print("1 - Поиск по биграмме во всех документах")
    print("2 - Вывести топ-20 биграмм по конкретному документу")
    print("3 - Извлечение коллокаций (прилагательное+существительное)")

    choice = input("\n👉 Ваш выбор (1/2/3): ").strip()

    if choice == '1':
        phrase = input("Введите фразу из 2 слов для поиска: ").strip()
        if phrase:
            search_bigrams(phrase)
        else:
            print("❌ Фраза не может быть пустой!")

    elif choice == '2':
        interactive_top_bigrams()

    elif choice == '3':
        interactive_collocations()

    else:
        print("❌ Неверный выбор! Запустите программу снова.")