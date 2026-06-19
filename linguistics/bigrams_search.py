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


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def get_all_documents_with_lemmas():
    """Получает все документы с лемматизированным текстом и названиями"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.type, dl.content
                FROM documents d
                INNER JOIN documents_lemmatized dl ON d.id = dl.id_documents
                WHERE dl.content IS NOT NULL AND dl.content != ''
                ORDER BY d.id
            """)
            documents = cur.fetchall()
        return documents
    except Exception as e:
        print(f"Ошибка при получении документов с леммами: {e}")
        return []
    finally:
        conn.close()


def get_document_info(doc_id: int):
    """Получает информацию о документе (название, тип)"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT title, type
                FROM documents 
                WHERE id = %s
            """, (doc_id,))
            result = cur.fetchone()
            if result:
                return {
                    'title': result[0],
                    'type': result[1]
                }
            return None
    except Exception as e:
        print(f"Ошибка при получении информации о документе: {e}")
        return None
    finally:
        conn.close()


def get_lemmatized_text(doc_id: int):
    """Получает лемматизированный текст из таблицы documents_lemmatized"""
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
    except Exception as e:
        print(f"Ошибка при получении лемматизированного текста: {e}")
        return None
    finally:
        conn.close()


def find_lemmatized_bigram_contexts(lemmatized_text: str, word1: str, word2: str, context_size: int = 70) -> list:
    """Находит ВСЕ контексты для биграммы в лемматизированном тексте"""
    contexts = []
    text_lower = lemmatized_text.lower()
    pattern = re.compile(rf'{re.escape(word1.lower())}\s+{re.escape(word2.lower())}')

    for match in pattern.finditer(text_lower):
        start = max(0, match.start() - context_size)
        end = min(len(lemmatized_text), match.end() + context_size)
        context = lemmatized_text[start:end].replace('\n', ' ')
        contexts.append(context)

    return contexts


def extract_bigrams_by_frequency(lemmatized_text: str, top_n: int = 50) -> list:
    """
    Извлекает биграммы из лемматизированного текста по частоте встречаемости
    """
    if not lemmatized_text:
        return []

    # Разбиваем лемматизированный текст на леммы
    tokens = lemmatized_text.lower().split()

    # Фильтруем стоп-слова и слишком короткие слова
    tokens = [t for t in tokens if t not in RUSSIAN_STOP_WORDS and len(t) > 1]

    if len(tokens) < 2:
        return []

    # Создаем finder для биграмм
    finder = BigramCollocationFinder.from_words(tokens)

    # Фильтруем редкие биграммы (встречаются менее 2 раз)
    finder.apply_freq_filter(2)

    # Получаем топ-N биграмм по частоте
    bigrams_freq = finder.nbest(BigramAssocMeasures.raw_freq, top_n)

    # Формируем результат: (биграмма, частота)
    result = []
    for bigram in bigrams_freq:
        freq = finder.ngram_fd[bigram]
        result.append((bigram, freq))

    return result


def extract_collocations_by_likelihood(lemmatized_text: str, top_n: int = 50) -> list:
    """
    Извлекает коллокации из лемматизированного текста по метрике Likelihood Ratio
    """
    if not lemmatized_text:
        return []

    # Разбиваем лемматизированный текст на леммы
    tokens = lemmatized_text.lower().split()

    # Фильтруем стоп-слова и слишком короткие слова
    tokens = [t for t in tokens if t not in RUSSIAN_STOP_WORDS and len(t) > 1]

    if len(tokens) < 2:
        return []

    # Создаем finder для биграмм
    finder = BigramCollocationFinder.from_words(tokens)

    # Фильтруем редкие биграммы (встречаются менее 2 раз)
    finder.apply_freq_filter(2)

    # Получаем топ-N биграмм по Likelihood Ratio
    scored_bigrams = finder.score_ngrams(BigramAssocMeasures.likelihood_ratio)

    # Формируем результат: (биграмма, частота, likelihood_score)
    result = []
    for bigram, score in scored_bigrams[:top_n]:
        freq = finder.ngram_fd[bigram]
        result.append((bigram, freq, score))

    return result


def search_bigrams_by_word(search_word: str, top_n: int = 30):
    """Поиск биграмм по частоте, содержащих заданное слово"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК БИГРАММ ПО ЧАСТОТЕ")
    print(f"{'=' * 70}")
    print(f"🔍 ПОИСК БИГРАММ, СОДЕРЖАЩИХ СЛОВО: '{search_word}'")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()

    # Лемматизируем искомое слово
    search_lemma = None
    try:
        parsed = morph.parse(search_word.lower())[0]
        search_lemma = parsed.normal_form
        print(f"🔑 Лемма слова: '{search_lemma}'")
    except Exception as e:
        print(f"⚠️ Не удалось определить лемму слова: {e}")
        search_lemma = search_word.lower()

    documents = get_all_documents_with_lemmas()

    if not documents:
        print("❌ Нет документов с лемматизированным текстом")
        return

    found_bigrams = []

    for doc_id, title, doc_type, lemmatized_text in documents:
        if not lemmatized_text:
            continue

        print(f"\n📄 Обработка документа: {title[:50] if title else 'Без названия'} (ID: {doc_id})")

        # Извлекаем биграммы по частоте
        bigrams = extract_bigrams_by_frequency(lemmatized_text, 100)

        # Фильтруем биграммы, содержащие искомую лемму
        filtered_bigrams = []
        for bigram, freq in bigrams:
            word1, word2 = bigram

            # Проверяем совпадение с леммой
            if word1 == search_lemma or word2 == search_lemma:
                filtered_bigrams.append((bigram, freq))

        if filtered_bigrams:
            for bigram, freq in filtered_bigrams:
                # Находим ВСЕ контексты для ТОЧНОЙ биграммы
                contexts = find_lemmatized_bigram_contexts(
                    lemmatized_text,
                    bigram[0],
                    bigram[1]
                )

                found_bigrams.append({
                    'doc_id': doc_id,
                    'title': title[:100] if title else "Без названия",
                    'type': doc_type if doc_type else "Не указан",
                    'bigram': bigram,
                    'bigram_text': f"{bigram[0]} {bigram[1]}",
                    'frequency': freq,
                    'contexts': contexts
                })

    # Сортируем по частоте (от большего к меньшему)
    found_bigrams.sort(key=lambda x: x['frequency'], reverse=True)

    print(f"\n✅ Найдено биграмм, содержащих лемму '{search_lemma}': {len(found_bigrams)}")

    if found_bigrams:
        print(f"\n📊 ТОП-{min(top_n, len(found_bigrams))} БИГРАММ С ЛЕММОЙ '{search_lemma}':")
        print(f"{'─' * 70}")

        for i, item in enumerate(found_bigrams[:top_n], 1):
            print(f"\n{i:2d}. Биграмма (леммы): \"{item['bigram_text']}\"")
            print(f"    Документ: {item['title']}")
            print(f"    ID документа: {item['doc_id']}")
            print(f"    Тип: {item['type']}")
            print(f"    Частота: {item['frequency']} раз(а)")
            print(f"    Количество контекстов: {len(item['contexts'])}")

            if len(item['contexts']) == item['frequency']:
                print(f"    ✅ Количество контекстов соответствует частоте")
            else:
                print(
                    f"    ⚠️ Количество контекстов ({len(item['contexts'])}) не совпадает с частотой ({item['frequency']})")

            if item['contexts']:
                print(f"    ВСЕ КОНТЕКСТЫ в лемматизированном тексте:")
                for j, ctx in enumerate(item['contexts'], 1):
                    ctx_clean = re.sub(r'\s+', ' ', ctx)
                    highlighted = ctx_clean.replace(
                        item['bigram_text'],
                        f"***{item['bigram_text']}***"
                    )
                    print(f"      {j}. ...{highlighted}...")
            else:
                print(f"    ⚠️ Контексты для точной биграммы не найдены")
    else:
        print(f"\n❌ Биграммы, содержащие лемму '{search_lemma}', не найдены")


def get_document_bigrams(doc_id: int, top_n: int = 50):
    """Получает топ-N биграмм по частоте для конкретного документа"""
    print(f"\n{'=' * 70}")
    print(f"📊 БИГРАММЫ ПО ЧАСТОТЕ")
    print(f"{'=' * 70}")
    print(f"📊 ТОП-{top_n} БИГРАММ В ДОКУМЕНТЕ ID: {doc_id}")
    print(f"{'=' * 70}")

    # Получаем информацию о документе
    doc_info = get_document_info(doc_id)
    if not doc_info:
        print(f"❌ Документ с ID {doc_id} не найден")
        return

    # Получаем лемматизированный текст
    lemmatized_text = get_lemmatized_text(doc_id)
    if not lemmatized_text:
        print(f"❌ Для документа ID {doc_id} нет лемматизированной версии")
        return

    print(f"\n📄 Информация о документе:")
    print(f"   ID: {doc_id}")
    print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
    print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
    print(f"   Размер лемматизированного текста: {len(lemmatized_text)} символов")

    # Извлекаем биграммы по частоте
    bigrams = extract_bigrams_by_frequency(lemmatized_text, top_n)

    if not bigrams:
        print(f"\n❌ Биграммы не найдены в документе")
        return

    print(f"\n📊 ТОП-{len(bigrams)} БИГРАММ ПО ЧАСТОТЕ:")
    print(f"{'─' * 70}")

    for i, (bigram, freq) in enumerate(bigrams, 1):
        bigram_text = ' '.join(bigram)

        # Находим ВСЕ контексты для биграммы
        contexts = find_lemmatized_bigram_contexts(
            lemmatized_text,
            bigram[0],
            bigram[1]
        )

        print(f"\n{i:2d}. Биграмма (леммы): \"{bigram_text}\"")
        print(f"    Частота: {freq} раз(а)")
        print(f"    Количество контекстов: {len(contexts)}")

        if len(contexts) == freq:
            print(f"    ✅ Количество контекстов соответствует частоте")
        else:
            print(f"    ⚠️ Количество контекстов ({len(contexts)}) не совпадает с частотой ({freq})")

        if contexts:
            print(f"    ВСЕ КОНТЕКСТЫ в лемматизированном тексте:")
            for j, ctx in enumerate(contexts, 1):
                ctx_clean = re.sub(r'\s+', ' ', ctx)
                highlighted = ctx_clean.replace(
                    bigram_text,
                    f"***{bigram_text}***"
                )
                print(f"      {j}. ...{highlighted}...")
        else:
            print(f"    ⚠️ Контексты для точной биграммы не найдены")

    # Статистика
    print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
    print(f"   Всего уникальных биграмм: {len(bigrams)}")
    if bigrams:
        print(f"   Самая частотная биграмма: '{' '.join(bigrams[0][0])}' ({bigrams[0][1]} раз)")


def search_collocations_by_likelihood(doc_id: int = None, top_n: int = 30):
    """
    Поиск коллокаций по метрике Likelihood Ratio

    Параметры:
    - doc_id: ID документа (если None, то поиск по всем документам)
    - top_n: количество коллокаций для вывода
    """
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК КОЛЛОКАЦИЙ ПО МЕТРИКЕ LIKELIHOOD RATIO")
    print(f"{'=' * 70}")

    if doc_id:
        print(f"📊 ПОИСК В ДОКУМЕНТЕ ID: {doc_id}")
    else:
        print(f"📊 ПОИСК ПО ВСЕМ ДОКУМЕНТАМ")
    print(f"{'=' * 70}")

    if doc_id:
        # Поиск в конкретном документе
        doc_info = get_document_info(doc_id)
        if not doc_info:
            print(f"❌ Документ с ID {doc_id} не найден")
            return

        lemmatized_text = get_lemmatized_text(doc_id)
        if not lemmatized_text:
            print(f"❌ Для документа ID {doc_id} нет лемматизированной версии")
            return

        print(f"\n📄 Информация о документе:")
        print(f"   ID: {doc_id}")
        print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
        print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
        print(f"   Размер лемматизированного текста: {len(lemmatized_text)} символов")

        # Извлекаем коллокации по Likelihood Ratio
        collocations = extract_collocations_by_likelihood(lemmatized_text, top_n)

        if not collocations:
            print(f"\n❌ Коллокации не найдены в документе")
            return

        print(f"\n📊 ТОП-{len(collocations)} КОЛЛОКАЦИЙ ПО LIKELIHOOD RATIO:")
        print(f"{'─' * 70}")

        for i, (bigram, freq, score) in enumerate(collocations, 1):
            bigram_text = ' '.join(bigram)
            contexts = find_lemmatized_bigram_contexts(
                lemmatized_text,
                bigram[0],
                bigram[1]
            )

            print(f"\n{i:2d}. Коллокация: \"{bigram_text}\"")
            print(f"    Частота: {freq} раз(а)")
            print(f"    Likelihood Ratio: {score:.4f}")
            print(f"    Количество контекстов: {len(contexts)}")

            if len(contexts) == freq:
                print(f"    ✅ Количество контекстов соответствует частоте")
            else:
                print(f"    ⚠️ Количество контекстов ({len(contexts)}) не совпадает с частотой ({freq})")

            if contexts:
                print(f"    ВСЕ КОНТЕКСТЫ в лемматизированном тексте:")
                for j, ctx in enumerate(contexts, 1):
                    ctx_clean = re.sub(r'\s+', ' ', ctx)
                    highlighted = ctx_clean.replace(
                        bigram_text,
                        f"***{bigram_text}***"
                    )
                    print(f"      {j}. ...{highlighted}...")
            else:
                print(f"    ⚠️ Контексты для точной коллокации не найдены")

        # Статистика
        print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
        print(f"   Всего уникальных коллокаций: {len(collocations)}")
        if collocations:
            print(f"   Лучшая коллокация: '{' '.join(collocations[0][0])}' (Likelihood: {collocations[0][2]:.4f})")

    else:
        # Поиск по всем документам
        documents = get_all_documents_with_lemmas()
        if not documents:
            print("❌ Нет документов с лемматизированным текстом")
            return

        all_collocations = []

        print(f"\n📊 ОБРАБОТКА ВСЕХ ДОКУМЕНТОВ:")
        print(f"{'─' * 70}")

        for doc_id, title, doc_type, lemmatized_text in documents:
            if not lemmatized_text:
                continue

            print(f"\n📄 Документ: {title[:50] if title else 'Без названия'} (ID: {doc_id})")

            # Извлекаем коллокации по Likelihood Ratio
            collocations = extract_collocations_by_likelihood(lemmatized_text, top_n)

            if collocations:
                print(f"   Тип: {doc_type if doc_type else 'Не указан'}")
                print(f"   Найдено коллокаций: {len(collocations)}")
                print(f"   Топ-{min(3, len(collocations))} коллокаций:")
                for i, (bigram, freq, score) in enumerate(collocations[:3], 1):
                    print(f"     {i}. {' '.join(bigram)} (частота: {freq}, Likelihood: {score:.4f})")
                if len(collocations) > 3:
                    print(f"     ... и еще {len(collocations) - 3} коллокаций")

                # Сохраняем для общей статистики
                for bigram, freq, score in collocations:
                    all_collocations.append({
                        'doc_id': doc_id,
                        'title': title[:100] if title else "Без названия",
                        'bigram': bigram,
                        'bigram_text': f"{bigram[0]} {bigram[1]}",
                        'frequency': freq,
                        'likelihood_score': score
                    })
            else:
                print(f"   ⚠️ Коллокации не найдены")

        # Общая статистика по всем документам
        if all_collocations:
            print(f"\n{'=' * 70}")
            print(f"📊 ОБЩАЯ СТАТИСТИКА ПО ВСЕМ ДОКУМЕНТАМ")
            print(f"{'=' * 70}")
            print(f"   Всего коллокаций: {len(all_collocations)}")

            # Топ-10 коллокаций по Likelihood Ratio
            all_collocations.sort(key=lambda x: x['likelihood_score'], reverse=True)
            print(f"\n   ТОП-10 КОЛЛОКАЦИЙ ПО LIKELIHOOD RATIO:")
            print(f"   {'─' * 60}")
            for i, item in enumerate(all_collocations[:10], 1):
                print(f"   {i:2d}. \"{item['bigram_text']}\" (Likelihood: {item['likelihood_score']:.4f}, "
                      f"частота: {item['frequency']})")
                print(f"       Документ: {item['title'][:60]} (ID: {item['doc_id']})")
        else:
            print(f"\n❌ Коллокации не найдены ни в одном документе")


def show_documents_list():
    """Показывает список всех документов для выбора"""
    documents = get_all_documents_with_lemmas()

    if not documents:
        print("❌ Нет доступных документов с лемматизированным текстом")
        return None

    print(f"\n{'=' * 70}")
    print("📚 СПИСОК ДОКУМЕНТОВ С ЛЕММАТИЗИРОВАННЫМ ТЕКСТОМ")
    print(f"{'=' * 70}")
    print(f"\n{'ID':<6} {'Тип':<12} {'Название'}")
    print(f"{'─' * 70}")

    for doc_id, title, doc_type, _ in documents:
        title_short = title[:50] if title else "Без названия"
        doc_type_short = doc_type[:10] if doc_type else "Не указан"
        print(f"{doc_id:<6} {doc_type_short:<12} {title_short}")

    return documents


def interactive_search():
    """Интерактивный режим для поиска"""
    print(f"\n{'=' * 60}")
    print("🔍 ПОИСК БИГРАММ И КОЛЛОКАЦИЙ")
    print(f"{'=' * 60}")

    print("\nВыберите режим работы:")
    print("1 - Поиск биграмм (по частоте), содержащих конкретное слово")
    print("2 - Показать топ-N биграмм (по частоте) в конкретном документе")
    print("3 - Показать все документы с их топ-биграммами (по частоте)")
    print("4 - Поиск коллокаций по Likelihood Ratio")

    choice = input("\n👉 Ваш выбор (1/2/3/4): ").strip()

    if choice == '1':
        search_word = input("Введите слово для поиска: ").strip()
        if search_word:
            search_bigrams_by_word(search_word)
        else:
            print("❌ Слово не может быть пустым!")

    elif choice == '2':
        documents = show_documents_list()
        if not documents:
            return

        while True:
            try:
                doc_id = input(f"\n👉 Введите ID документа: ").strip()
                doc_id = int(doc_id)

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

        while True:
            try:
                top_n = input(f"\n👉 Введите количество биграмм для вывода (по умолчанию 30): ").strip()
                if not top_n:
                    top_n = 30
                    break
                top_n = int(top_n)
                if 1 <= top_n <= 100:
                    break
                else:
                    print("❌ Пожалуйста, введите число от 1 до 100")
            except ValueError:
                print("❌ Пожалуйста, введите корректное число")

        get_document_bigrams(doc_id, top_n)

    elif choice == '3':
        while True:
            try:
                top_n = input(f"\n👉 Введите количество биграмм для каждого документа (по умолчанию 20): ").strip()
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

        documents = get_all_documents_with_lemmas()
        if not documents:
            print("❌ Нет документов с лемматизированным текстом")
            return

        print(f"\n{'=' * 70}")
        print(f"📊 ТОП-{top_n} БИГРАММ ПО ЧАСТОТЕ ДЛЯ ВСЕХ ДОКУМЕНТОВ")
        print(f"{'=' * 70}")

        for doc_id, title, doc_type, lemmatized_text in documents:
            if not lemmatized_text:
                continue

            bigrams = extract_bigrams_by_frequency(lemmatized_text, top_n)

            print(f"\n📄 Документ: {title[:80] if title else 'Без названия'} (ID: {doc_id})")
            print(f"   Тип: {doc_type if doc_type else 'Не указан'}")

            if bigrams:
                print(f"   Топ-{min(5, len(bigrams))} биграмм:")
                for i, (bigram, freq) in enumerate(bigrams[:5], 1):
                    print(f"     {i}. {' '.join(bigram)} (частота: {freq})")
                if len(bigrams) > 5:
                    print(f"     ... и еще {len(bigrams) - 5} биграмм")
            else:
                print("   ⚠️ Биграммы не найдены")

    elif choice == '4':
        print("\nВыберите режим поиска коллокаций:")
        print("1 - Поиск по всем документам")
        print("2 - Поиск в конкретном документе")

        sub_choice = input("\n👉 Ваш выбор (1/2): ").strip()

        if sub_choice == '1':
            while True:
                try:
                    top_n = input(f"\n👉 Введите количество коллокаций для каждого документа (по умолчанию 30): ").strip()
                    if not top_n:
                        top_n = 30
                        break
                    top_n = int(top_n)
                    if 1 <= top_n <= 100:
                        break
                    else:
                        print("❌ Пожалуйста, введите число от 1 до 100")
                except ValueError:
                    print("❌ Пожалуйста, введите корректное число")

            search_collocations_by_likelihood(doc_id=None, top_n=top_n)

        elif sub_choice == '2':
            documents = show_documents_list()
            if not documents:
                return

            while True:
                try:
                    doc_id = input(f"\n👉 Введите ID документа: ").strip()
                    doc_id = int(doc_id)

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

            while True:
                try:
                    top_n = input(f"\n👉 Введите количество коллокаций для вывода (по умолчанию 30): ").strip()
                    if not top_n:
                        top_n = 30
                        break
                    top_n = int(top_n)
                    if 1 <= top_n <= 100:
                        break
                    else:
                        print("❌ Пожалуйста, введите число от 1 до 100")
                except ValueError:
                    print("❌ Пожалуйста, введите корректное число")

            search_collocations_by_likelihood(doc_id=doc_id, top_n=top_n)

        else:
            print("❌ Неверный выбор!")

    else:
        print("❌ Неверный выбор!")


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА БИГРАММ И КОЛЛОКАЦИЙ")
    print("=" * 60)
    interactive_search()