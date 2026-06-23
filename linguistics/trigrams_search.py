import psycopg2
from nltk.tokenize import word_tokenize
from nltk.collocations import TrigramCollocationFinder
from nltk.metrics import TrigramAssocMeasures
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

# Подключение к БД
from db_connection import connect_db, DB_CONFIG

RUSSIAN_STOP_WORDS = set(stopwords.words('russian'))


def get_all_documents_with_lemmas():
    """Получает все документы с лемматизированным текстом и оригинальным содержимым"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.type, dl.content, d.content
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


def get_original_content(doc_id: int):
    """Получает оригинальный текст документа"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT content
                FROM documents 
                WHERE id = %s
            """, (doc_id,))
            result = cur.fetchone()
            if result:
                return result[0]
            return None
    except Exception as e:
        print(f"Ошибка при получении оригинального текста: {e}")
        return None
    finally:
        conn.close()


def find_original_trigram_contexts(original_text: str, word1: str, word2: str, word3: str, morph,
                                   context_size: int = 150) -> list:
    """
    Находит ВСЕ контексты для триграммы в ОРИГИНАЛЬНОМ тексте
    Ищет все возможные формы слов
    """
    contexts = set()
    text_lower = original_text.lower()

    # Получаем все формы для первого слова
    try:
        parsed1 = morph.parse(word1)[0]
        forms1 = [form.word for form in parsed1.lexeme]
        if word1 not in forms1:
            forms1.append(word1)
    except:
        forms1 = [word1]

    # Получаем все формы для второго слова
    try:
        parsed2 = morph.parse(word2)[0]
        forms2 = [form.word for form in parsed2.lexeme]
        if word2 not in forms2:
            forms2.append(word2)
    except:
        forms2 = [word2]

    # Получаем все формы для третьего слова
    try:
        parsed3 = morph.parse(word3)[0]
        forms3 = [form.word for form in parsed3.lexeme]
        if word3 not in forms3:
            forms3.append(word3)
    except:
        forms3 = [word3]

    # Ищем все комбинации форм
    for form1 in forms1:
        for form2 in forms2:
            for form3 in forms3:
                pattern = re.compile(
                    rf'{re.escape(form1.lower())}\s+{re.escape(form2.lower())}\s+{re.escape(form3.lower())}',
                    re.IGNORECASE
                )
                for match in pattern.finditer(text_lower):
                    start = max(0, match.start() - context_size)
                    end = min(len(original_text), match.end() + context_size)
                    context = original_text[start:end].replace('\n', ' ')
                    contexts.add(context)

    return list(contexts)


def extract_trigrams_from_lemmatized(lemmatized_text: str, top_n: int = 50) -> list:
    if not lemmatized_text:
        return []
    tokens = lemmatized_text.lower().split()
    tokens = [t for t in tokens if t not in RUSSIAN_STOP_WORDS and len(t) > 1]
    if len(tokens) < 3:
        return []
    finder = TrigramCollocationFinder.from_words(tokens)
    finder.apply_freq_filter(2)
    trigrams_freq = finder.nbest(TrigramAssocMeasures.raw_freq, top_n)
    result = []
    for trigram in trigrams_freq:
        freq = finder.ngram_fd[trigram]
        result.append((trigram, freq))
    return result


def search_trigrams_by_word(search_word: str, top_n: int = 30):
    """Поиск триграмм, содержащих заданное слово (по частоте)"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ТРИГРАММ ПО ЧАСТОТЕ")
    print(f"{'=' * 70}")
    print(f"🔍 ПОИСК ТРИГРАММ, СОДЕРЖАЩИХ СЛОВО: '{search_word}'")
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

    found_trigrams = []

    for doc_id, title, doc_type, lemmatized_text, original_content in documents:
        if not lemmatized_text or not original_content:
            continue

        print(f"\n📄 Обработка документа: {title[:50] if title else 'Без названия'} (ID: {doc_id})")

        # Извлекаем триграммы по частоте
        trigrams = extract_trigrams_from_lemmatized(lemmatized_text, 100)

        # Фильтруем триграммы, содержащие искомую лемму
        filtered_trigrams = []
        for trigram, freq in trigrams:
            word1, word2, word3 = trigram

            # Проверяем совпадение с леммой
            if word1 == search_lemma or word2 == search_lemma or word3 == search_lemma:
                filtered_trigrams.append((trigram, freq))

        if filtered_trigrams:
            for trigram, freq in filtered_trigrams:
                # Находим контексты в ОРИГИНАЛЬНОМ тексте
                contexts = find_original_trigram_contexts(
                    original_content,
                    trigram[0],
                    trigram[1],
                    trigram[2],
                    morph,
                    150
                )
                contexts = contexts[:freq]  # Обрезаем до частоты

                found_trigrams.append({
                    'doc_id': doc_id,
                    'title': title[:100] if title else "Без названия",
                    'type': doc_type if doc_type else "Не указан",
                    'trigram': trigram,
                    'trigram_text': f"{trigram[0]} {trigram[1]} {trigram[2]}",
                    'frequency': freq,
                    'contexts': contexts
                })

    # Сортируем по частоте (от большего к меньшему)
    found_trigrams.sort(key=lambda x: x['frequency'], reverse=True)

    print(f"\n✅ Найдено триграмм, содержащих лемму '{search_lemma}': {len(found_trigrams)}")

    if found_trigrams:
        print(f"\n📊 ТОП-{min(top_n, len(found_trigrams))} ТРИГРАММ С ЛЕММОЙ '{search_lemma}':")
        print(f"{'─' * 70}")

        for i, item in enumerate(found_trigrams[:top_n], 1):
            print(f"\n{i:2d}. Триграмма (леммы): \"{item['trigram_text']}\"")
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
                print(f"    ВСЕ КОНТЕКСТЫ (в оригинальном тексте):")
                for j, ctx in enumerate(item['contexts'], 1):
                    ctx_clean = re.sub(r'\s+', ' ', ctx)
                    print(f"      {j}. ...{ctx_clean}...")
            else:
                print(f"    ⚠️ Контексты для точной триграммы не найдены")
    else:
        print(f"\n❌ Триграммы, содержащие лемму '{search_lemma}', не найдены")


def get_document_trigrams(doc_id: int, top_n: int = 50):
    """Получает топ-N триграмм для конкретного документа по частоте"""
    print(f"\n{'=' * 70}")
    print(f"📊 ТРИГРАММЫ ПО ЧАСТОТЕ")
    print(f"{'=' * 70}")
    print(f"📊 ТОП-{top_n} ТРИГРАММ В ДОКУМЕНТЕ ID: {doc_id}")
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

    original_content = get_original_content(doc_id)
    if not original_content:
        print(f"❌ Для документа ID {doc_id} нет оригинального текста")
        return

    print(f"\n📄 Информация о документе:")
    print(f"   ID: {doc_id}")
    print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
    print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
    print(f"   Размер лемматизированного текста: {len(lemmatized_text)} символов")

    # Извлекаем триграммы по частоте
    trigrams = extract_trigrams_from_lemmatized(lemmatized_text, top_n)

    if not trigrams:
        print(f"\n❌ Триграммы не найдены в документе")
        return

    print(f"\n📊 ТОП-{len(trigrams)} ТРИГРАММ ПО ЧАСТОТЕ:")
    print(f"{'─' * 70}")

    morph = MorphAnalyzer()

    for i, (trigram, freq) in enumerate(trigrams, 1):
        trigram_text = ' '.join(trigram)

        # Находим контексты в ОРИГИНАЛЬНОМ тексте
        contexts = find_original_trigram_contexts(
            original_content,
            trigram[0],
            trigram[1],
            trigram[2],
            morph,
            150
        )
        contexts = contexts[:freq]  # Обрезаем до частоты

        print(f"\n{i:2d}. Триграмма (леммы): \"{trigram_text}\"")
        print(f"    Частота: {freq} раз(а)")
        print(f"    Количество контекстов: {len(contexts)}")

        if len(contexts) == freq:
            print(f"    ✅ Количество контекстов соответствует частоте")
        else:
            print(f"    ⚠️ Количество контекстов ({len(contexts)}) не совпадает с частотой ({freq})")

        if contexts:
            print(f"    ВСЕ КОНТЕКСТЫ (в оригинальном тексте):")
            for j, ctx in enumerate(contexts, 1):
                ctx_clean = re.sub(r'\s+', ' ', ctx)
                print(f"      {j}. ...{ctx_clean}...")
        else:
            print(f"    ⚠️ Контексты для точной триграммы не найдены")

    # Статистика
    print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
    print(f"   Всего уникальных триграмм: {len(trigrams)}")
    if trigrams:
        print(f"   Самая частотная триграмма: '{' '.join(trigrams[0][0])}' ({trigrams[0][1]} раз)")


def search_trigrams_by_frequency(doc_id: int = None, top_n: int = 30):
    """
    Поиск триграмм по частоте

    Параметры:
    - doc_id: ID документа (если None, то поиск по всем документам)
    - top_n: количество триграмм для вывода
    """
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ТРИГРАММ ПО ЧАСТОТЕ")
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

        original_content = get_original_content(doc_id)
        if not original_content:
            print(f"❌ Для документа ID {doc_id} нет оригинального текста")
            return

        print(f"\n📄 Информация о документе:")
        print(f"   ID: {doc_id}")
        print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
        print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
        print(f"   Размер лемматизированного текста: {len(lemmatized_text)} символов")

        # Извлекаем триграммы по частоте
        trigrams = extract_trigrams_from_lemmatized(lemmatized_text, top_n)

        if not trigrams:
            print(f"\n❌ Триграммы не найдены в документе")
            return

        print(f"\n📊 ТОП-{len(trigrams)} ТРИГРАММ ПО ЧАСТОТЕ:")
        print(f"{'─' * 70}")

        morph = MorphAnalyzer()

        for i, (trigram, freq) in enumerate(trigrams, 1):
            trigram_text = ' '.join(trigram)
            contexts = find_original_trigram_contexts(
                original_content,
                trigram[0],
                trigram[1],
                trigram[2],
                morph,
                150
            )
            contexts = contexts[:freq]  # Обрезаем до частоты

            print(f"\n{i:2d}. Триграмма: \"{trigram_text}\"")
            print(f"    Частота: {freq} раз(а)")
            print(f"    Количество контекстов: {len(contexts)}")

            if len(contexts) == freq:
                print(f"    ✅ Количество контекстов соответствует частоте")
            else:
                print(f"    ⚠️ Количество контекстов ({len(contexts)}) не совпадает с частотой ({freq})")

            if contexts:
                print(f"    ВСЕ КОНТЕКСТЫ (в оригинальном тексте):")
                for j, ctx in enumerate(contexts, 1):
                    ctx_clean = re.sub(r'\s+', ' ', ctx)
                    print(f"      {j}. ...{ctx_clean}...")
            else:
                print(f"    ⚠️ Контексты для точной триграммы не найдены")

        # Статистика
        print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
        print(f"   Всего уникальных триграмм: {len(trigrams)}")
        if trigrams:
            print(f"   Самая частотная триграмма: '{' '.join(trigrams[0][0])}' ({trigrams[0][1]} раз)")

    else:
        # Поиск по всем документам
        documents = get_all_documents_with_lemmas()
        if not documents:
            print("❌ Нет документов с лемматизированным текстом")
            return

        all_trigrams = []

        print(f"\n📊 ОБРАБОТКА ВСЕХ ДОКУМЕНТОВ:")
        print(f"{'─' * 70}")

        for doc_id, title, doc_type, lemmatized_text, _ in documents:
            if not lemmatized_text:
                continue

            print(f"\n📄 Документ: {title[:50] if title else 'Без названия'} (ID: {doc_id})")

            # Извлекаем триграммы по частоте
            trigrams = extract_trigrams_from_lemmatized(lemmatized_text, top_n)

            if trigrams:
                print(f"   Тип: {doc_type if doc_type else 'Не указан'}")
                print(f"   Найдено триграмм: {len(trigrams)}")
                print(f"   Топ-{min(3, len(trigrams))} триграмм:")
                for i, (trigram, freq) in enumerate(trigrams[:3], 1):
                    print(f"     {i}. {' '.join(trigram)} (частота: {freq})")
                if len(trigrams) > 3:
                    print(f"     ... и еще {len(trigrams) - 3} триграмм")

                # Сохраняем для общей статистики
                for trigram, freq in trigrams:
                    all_trigrams.append({
                        'doc_id': doc_id,
                        'title': title[:100] if title else "Без названия",
                        'trigram': trigram,
                        'trigram_text': f"{trigram[0]} {trigram[1]} {trigram[2]}",
                        'frequency': freq
                    })
            else:
                print(f"   ⚠️ Триграммы не найдены")

        # Общая статистика по всем документам
        if all_trigrams:
            print(f"\n{'=' * 70}")
            print(f"📊 ОБЩАЯ СТАТИСТИКА ПО ВСЕМ ДОКУМЕНТАМ")
            print(f"{'=' * 70}")
            print(f"   Всего триграмм: {len(all_trigrams)}")

            # Топ-10 триграмм по частоте
            all_trigrams.sort(key=lambda x: x['frequency'], reverse=True)
            print(f"\n   ТОП-10 ТРИГРАММ ПО ЧАСТОТЕ:")
            print(f"   {'─' * 60}")
            for i, item in enumerate(all_trigrams[:10], 1):
                print(f"   {i:2d}. \"{item['trigram_text']}\" (частота: {item['frequency']})")
                print(f"       Документ: {item['title'][:60]} (ID: {item['doc_id']})")
        else:
            print(f"\n❌ Триграммы не найдены ни в одном документе")


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

    for doc_id, title, doc_type, _, _ in documents:
        title_short = title[:50] if title else "Без названия"
        doc_type_short = doc_type[:10] if doc_type else "Не указан"
        print(f"{doc_id:<6} {doc_type_short:<12} {title_short}")

    return documents


def interactive_search():
    """Интерактивный режим для поиска"""
    print(f"\n{'=' * 60}")
    print("🔍 ПОИСК ТРИГРАММ ПО ЧАСТОТЕ")
    print(f"{'=' * 60}")
    print("ℹ️  Леммы выводятся в нормальной форме")
    print("ℹ️  Контексты показываются в оригинальном виде")
    print("=" * 60)

    print("\nВыберите режим работы с триграммами:")
    print("1 - Поиск триграмм, содержащих конкретное слово")
    print("2 - Показать топ-N триграмм в конкретном документе")
    print("3 - Поиск триграмм по всем документам")

    choice = input("\n👉 Ваш выбор (1/2/3): ").strip()

    if choice == '1':
        search_word = input("Введите слово для поиска: ").strip()
        if search_word:
            search_trigrams_by_word(search_word)
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
                top_n = input(f"\n👉 Введите количество триграмм для вывода (по умолчанию 30): ").strip()
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

        get_document_trigrams(doc_id, top_n)

    elif choice == '3':
        while True:
            try:
                top_n = input(f"\n👉 Введите количество триграмм для каждого документа (по умолчанию 30): ").strip()
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

        search_trigrams_by_frequency(doc_id=None, top_n=top_n)

    else:
        print("❌ Неверный выбор!")


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА ТРИГРАММ ПО ЧАСТОТЕ")
    print("=" * 60)
    interactive_search()