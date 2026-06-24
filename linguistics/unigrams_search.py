import psycopg2
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from pymorphy3 import MorphAnalyzer
import nltk
import re
from collections import Counter
import json

# Скачиваем необходимые данные
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('stopwords', quiet=True)

# Подключение к БД
from db_connection import connect_db, DB_CONFIG

# Базовые стоп-слова из NLTK
RUSSIAN_STOP_WORDS = set(stopwords.words('russian'))

# Дополнительные стоп-слова для фильтрации
EXTRA_STOP_WORDS = {
    # Предлоги
    'без', 'в', 'для', 'до', 'за', 'из', 'к', 'на', 'над', 'о', 'об', 'от', 'по',
    'под', 'при', 'про', 'с', 'со', 'у', 'через', 'между', 'ради', 'сквозь',
    'вокруг', 'около', 'возле', 'близ', 'вдоль', 'мимо', 'напротив', 'позади',
    'посреди', 'среди', 'сверх', 'через', 'вследствие', 'благодаря', 'несмотря',
    'ввиду', 'вместо', 'вроде', 'насчет', 'относительно', 'согласно', 'сообразно',
    'вслед', 'навстречу', 'наперекор', 'наподобие', 'помимо', 'после', 'прежде',
    'против', 'среди', 'у', 'через',

    # Союзы
    'а', 'и', 'или', 'но', 'да', 'же', 'либо', 'то', 'того', 'так', 'как',
    'что', 'чтобы', 'будто', 'словно', 'точно', 'как-будто', 'также', 'зато',
    'однако', 'причем', 'притом', 'потому', 'поэтому', 'оттого', 'зачем', 'почему',

    # Частицы
    'не', 'ни', 'бы', 'б', 'же', 'ж', 'ли', 'ль', 'уж', 'вот', 'вон', 'ведь',
    'даже', 'уже', 'еще', 'ещё', 'почти', 'только', 'лишь', 'хоть', 'хотя',
    'пусть', 'пускай', 'авось', 'небось', 'мол', 'де', 'дескать', 'также',

    # Местоимения
    'я', 'ты', 'он', 'она', 'оно', 'мы', 'вы', 'они', 'себя',
    'меня', 'тебя', 'его', 'ее', 'нас', 'вас', 'их',
    'мне', 'тебе', 'ему', 'ей', 'нам', 'вам', 'им',
    'мой', 'твой', 'свой', 'наш', 'ваш', 'его', 'ее', 'их',
    'этот', 'эта', 'это', 'эти', 'тот', 'та', 'то', 'те',
    'весь', 'вся', 'все', 'всё', 'всех', 'всем', 'всеми',
    'сам', 'сама', 'само', 'сами', 'который', 'которая', 'которое', 'которые',

    # Глаголы-связки
    'быть', 'являться', 'стать', 'становиться', 'находиться', 'называться',
    'оказаться', 'оказываться', 'представлять', 'представляться',

    # Вспомогательные слова
    'это', 'этот', 'эта', 'это', 'эти', 'того', 'тому', 'тем', 'том',
    'этим', 'этой', 'этих', 'этим', 'этими',

    # Слова-паразиты
    'так', 'ну', 'вот', 'типа', 'как', 'бы', 'как-то', 'что-то',
    'где-то', 'когда-то', 'кто-то', 'что-нибудь', 'как-нибудь',

    # Междометия
    'ой', 'ай', 'ух', 'ах', 'эх', 'ох', 'ну',

    # Другие часто встречаемые слова
    'год', 'года', 'лет', 'месяц', 'день', 'ночь', 'утро', 'вечер',
    'раз', 'два', 'три', 'четыре', 'пять', 'один', 'одна', 'одно',
    'другой', 'другая', 'другое', 'другие', 'разный', 'разные',
    'также', 'ещё', 'еще', 'уже', 'тоже', 'либо', 'кроме', 'включая',
    'включая', 'исключая', 'более', 'менее', 'очень', 'слишком',
    'достаточно', 'совсем', 'вполне', 'абсолютно', 'почти', 'около',
    'примерно', 'ровно', 'точно', 'аккуратно', 'осторожно',

    # Короткие слова (фильтруются отдельно)
    'в', 'и', 'на', 'с', 'к', 'у', 'о', 'об', 'от', 'до', 'за', 'из',
    'под', 'над', 'во', 'ко', 'со', 'обо', 'подо', 'надо', 'предо',

    # Вопросительные слова
    'что', 'кто', 'где', 'куда', 'откуда', 'когда', 'почему', 'зачем',
    'как', 'какой', 'какая', 'какое', 'какие', 'сколько', 'насколько',

    # Относительные слова
    'который', 'которая', 'которое', 'которые', 'которого', 'которой',
    'которых', 'которым', 'которыми', 'чей', 'чья', 'чье', 'чьи',
}

# Объединяем все стоп-слова
STOP_WORDS = RUSSIAN_STOP_WORDS | EXTRA_STOP_WORDS

ABBREVIATIONS = {
    'ИжГТУ': 'ижгту', 'ижгту': 'ижгту', 'ими': 'ими',
}

PROTECTED_WORDS = {'ижгту'}


def get_all_documents():
    """Получает список всех документов из БД с информацией о лемматизации"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.type, 
                       CASE WHEN dl.content IS NOT NULL THEN true ELSE false END as has_lemmas
                FROM documents d
                LEFT JOIN documents_lemmatized dl ON d.id = dl.id_documents
                WHERE d.content IS NOT NULL AND d.content != ''
                ORDER BY d.id
            """)
            documents = cur.fetchall()
        return documents
    except Exception as e:
        print(f"Ошибка при получении списка документов: {e}")
        return []
    finally:
        conn.close()


def get_document_content(doc_id: int):
    """Получает содержимое документа из таблицы documents"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT title, content, type 
                FROM documents 
                WHERE id = %s
            """, (doc_id,))
            result = cur.fetchone()
            if result:
                return {
                    'title': result[0],
                    'content': result[1],
                    'type': result[2]
                }
            return None
    except Exception as e:
        print(f"Ошибка при получении документа: {e}")
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


def get_all_documents_with_lemmas():
    """Получает все документы с лемматизированным текстом и оригинальным содержимым"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.type, dl.content, d.content
                FROM documents d
                INNER JOIN documents_lemmatized dl ON d.id = dl.id_documents
                WHERE d.content IS NOT NULL AND d.content != ''
                ORDER BY d.id
            """)
            documents = cur.fetchall()
        return documents
    except Exception as e:
        print(f"Ошибка при получении документов с леммами: {e}")
        return []
    finally:
        conn.close()


def lemmatize_text(text: str, morph) -> list:
    """Лемматизация текста (для поискового запроса)"""
    if not text:
        return []

    # Очистка текста
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = word_tokenize(text.lower(), language='russian')
    tokens = [t for t in tokens if t.isalpha() and t not in STOP_WORDS]

    lemmas = []
    for token in tokens:
        if token in PROTECTED_WORDS:
            lemmas.append(token)
            continue
        try:
            lemma = morph.parse(token)[0].normal_form
            if len(lemma) >= 2 and lemma not in STOP_WORDS:
                lemmas.append(lemma)
        except Exception:
            pass

    return lemmas


def find_all_contexts_original(text: str, word: str, context_size: int = 70) -> list:
    """
    Находит все контексты для слова в оригинальном тексте
    """
    contexts = []
    text_lower = text.lower()
    pos = 0
    word_lower = word.lower()

    while True:
        found = text_lower.find(word_lower, pos)
        if found == -1:
            break
        start = max(0, found - context_size)
        end = min(len(text), found + len(word) + context_size)
        contexts.append(text[start:end].replace('\n', ' '))
        pos = found + 1

    return contexts


def find_all_contexts_by_lemma(text: str, lemma: str, morph, context_size: int = 70) -> list:
    """
    Находит все контексты для леммы в оригинальном тексте
    Ищет все возможные формы слова
    """
    contexts = set()  # Используем set для уникальности
    text_lower = text.lower()

    # Получаем все формы слова
    try:
        parsed = morph.parse(lemma)[0]
        # Все формы слова (разные падежи, числа и т.д.)
        word_forms = [form.word for form in parsed.lexeme]
        # Добавляем саму лемму
        if lemma not in word_forms:
            word_forms.append(lemma)
    except Exception:
        word_forms = [lemma]

    # Ищем каждую форму в тексте
    for form in word_forms:
        form_lower = form.lower()
        pos = 0
        while True:
            found = text_lower.find(form_lower, pos)
            if found == -1:
                break
            start = max(0, found - context_size)
            end = min(len(text), found + len(form) + context_size)
            context = text[start:end].replace('\n', ' ')
            contexts.add(context)
            pos = found + 1

    return list(contexts)


def is_stop_word(word: str) -> bool:
    """Проверяет, является ли слово стоп-словом"""
    word_lower = word.lower()
    return word_lower in STOP_WORDS or len(word_lower) <= 2


def search_unigrams(search_word: str, limit: int = 20):
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
        print(f"🔑 Лемма для поиска: '{search_lemma}'")
        # Получаем все документы с лемматизированным текстом и оригиналом
        documents = get_all_documents_with_lemmas()
        if not documents:
            print("❌ Нет документов с лемматизированным текстом")
            return
        results = []
        for doc_id, title, doc_type, lemmatized_text, original_content in documents:
            if not lemmatized_text or not original_content:
                continue
            # Разбиваем лемматизированный текст на леммы
            lemmas_list = lemmatized_text.split()
            # Фильтруем стоп-слова
            lemmas_list = [l for l in lemmas_list if not is_stop_word(l)]

            # Подсчитываем частоту леммы
            freq = lemmas_list.count(search_lemma)

            if freq > 0:
                # Находим ВСЕ контексты в ОРИГИНАЛЬНОМ тексте по лемме
                contexts = find_all_contexts_by_lemma(original_content, search_lemma, morph, 70)

                # Если контекстов меньше, пробуем прямой поиск
                if len(contexts) < freq:
                    direct_contexts = find_all_contexts_original(original_content, search_word, 70)
                    for ctx in direct_contexts:
                        if ctx not in contexts:
                            contexts.append(ctx)

                # Обрезаем до частоты, если контекстов больше
                contexts = contexts[:freq]

                results.append({
                    'id': doc_id,
                    'title': title[:150] if title else "Без названия",
                    'type': doc_type if doc_type else "Не указан",
                    'frequency': freq,
                    'total_lemmas': len(lemmas_list),
                    'contexts': contexts
                })

        results.sort(key=lambda x: x['frequency'], reverse=True)

        print(f"\n✅ Найдено документов: {len(results[:limit])}")
        for r in results[:limit]:
            print(f"\n📄 Документ ID: {r['id']}")
            print(f"   Название: {r['title']}")
            print(f"   Тип файла: {r['type']}")
            print(f"   Частота вхождения леммы '{search_lemma}': {r['frequency']}")
            print(f"   Всего лемм в документе: {r['total_lemmas']}")
            print(f"   Всего контекстов: {len(r['contexts'])}")

            if len(r['contexts']) == r['frequency']:
                print(f"   ✅ Количество контекстов соответствует частоте")
            else:
                print(f"   ⚠️ Количество контекстов ({len(r['contexts'])}) не совпадает с частотой ({r['frequency']})")

            print(f"   {'─' * 50}")
            if r['contexts']:
                for i, ctx in enumerate(r['contexts'], 1):
                    ctx_clean = re.sub(r'\s+', ' ', ctx)
                    print(f"   Контекст {i}: ...{ctx_clean}...")
            else:
                print("   Контексты не найдены")
            print(f"   {'─' * 50}")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()


def get_top_unigrams_in_document(doc_id: int, top_n: int = 20):
    """Выводит топ-N самых часто встречаемых униграмм в конкретном документе"""
    print(f"\n{'=' * 60}")
    print(f"📊 ТОП-{top_n} УНИГРАММ В ДОКУМЕНТЕ ID: {doc_id}")
    print(f"{'=' * 60}")

    try:
        doc_info = get_document_content(doc_id)
        if not doc_info:
            print(f"❌ Документ с ID {doc_id} не найден")
            return

        lemmatized_text = get_lemmatized_text(doc_id)
        if not lemmatized_text:
            print(f"❌ Для документа ID {doc_id} нет лемматизированной версии")
            print("   Сначала запустите скрипт для лемматизации документов")
            return

        print(f"\n📄 Информация о документе:")
        print(f"   ID: {doc_id}")
        print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
        print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
        print(f"   Размер текста: {len(doc_info['content'])} символов")

        print(f"\n🔄 Обработка лемматизированного текста...")
        lemmas_list = lemmatized_text.split()
        print(f"   Всего лемм в документе: {len(lemmas_list)}")

        # Фильтруем стоп-слова
        lemmas_list_filtered = [l for l in lemmas_list if not is_stop_word(l)]
        print(f"   Лемм после фильтрации стоп-слов: {len(lemmas_list_filtered)}")

        # Подсчитываем частоту каждой леммы
        lemma_freq = Counter(lemmas_list_filtered)

        # Получаем топ-N лемм
        top_lemmas = lemma_freq.most_common(top_n)

        print(f"\n📊 ТОП-{top_n} САМЫХ ЧАСТЫХ УНИГРАММ (ЛЕММ):")
        print(f"   (стоп-слова и короткие слова удалены)")
        print(f"   (контексты показаны в оригинальном виде)")
        print(f"{'─' * 60}")

        morph = MorphAnalyzer()

        for i, (lemma, freq) in enumerate(top_lemmas, 1):
            # Находим ВСЕ контексты в ОРИГИНАЛЬНОМ тексте по лемме
            contexts = []
            if doc_info['content']:
                # Ищем все формы слова в оригинальном тексте
                contexts = find_all_contexts_by_lemma(doc_info['content'], lemma, morph, 60)

                # Если контекстов меньше, пробуем прямой поиск леммы
                if len(contexts) < freq:
                    direct_contexts = find_all_contexts_original(doc_info['content'], lemma, 60)
                    for ctx in direct_contexts:
                        if ctx not in contexts:
                            contexts.append(ctx)

            # Обрезаем до частоты, если контекстов больше
            contexts = contexts[:freq]

            print(f"\n{i:2d}. Лемма: \"{lemma}\"")
            print(f"    Частота: {freq} раз(а)")
            print(f"    Всего контекстов: {len(contexts)}")

            if len(contexts) == freq:
                print(f"    ✅ Количество контекстов соответствует частоте")
            else:
                print(f"    ⚠️ Количество контекстов ({len(contexts)}) не совпадает с частотой ({freq})")

            if contexts:
                print(f"    Контексты (оригинальный текст):")
                for j, ctx in enumerate(contexts, 1):
                    ctx_clean = re.sub(r'\s+', ' ', ctx)
                    print(f"      {j}. ...{ctx_clean[:150]}...")
                    if len(ctx_clean) > 150:
                        print(f"         ...{ctx_clean[150:]}...")
            else:
                print("    Контексты не найдены")

        print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
        print(f"   Всего уникальных лемм: {len(lemma_freq)}")
        print(f"   Всего лемм (с повторениями): {len(lemmas_list_filtered)}")
        if top_lemmas:
            print(f"   Самая частотная лемма: '{top_lemmas[0][0]}' ({top_lemmas[0][1]} раз)")
            if len(top_lemmas) > 1:
                print(f"   Вторая по частотности: '{top_lemmas[1][0]}' ({top_lemmas[1][1]} раз)")

        print(f"\n💡 Список стоп-слов включает {len(STOP_WORDS)} слов")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


def show_documents_list():
    """Показывает список всех документов для выбора"""
    documents = get_all_documents()

    if not documents:
        print("❌ Нет доступных документов")
        return None

    print(f"\n{'=' * 70}")
    print("📚 СПИСОК ДОСТУПНЫХ ДОКУМЕНТОВ")
    print(f"{'=' * 70}")
    print(f"\n{'ID':<6} {'Тип':<12} {'Лемматизирован':<18} {'Название'}")
    print(f"{'─' * 70}")

    for doc_id, title, doc_type, has_lemmas in documents:
        title_short = title[:50] if title else "Без названия"
        doc_type_short = doc_type[:10] if doc_type else "Не указан"
        has_lemmas_str = "✅ Да" if has_lemmas else "❌ Нет"
        print(f"{doc_id:<6} {doc_type_short:<12} {has_lemmas_str:<18} {title_short}")

    return documents


def interactive_top_unigrams():
    """Интерактивный режим для выбора документа и вывода топ униграмм"""
    print(f"\n{'=' * 60}")
    print("🏆 ВЫВОД ТОП-20 УНИГРАММ ПО ДОКУМЕНТУ")
    print(f"{'=' * 60}")
    print("ℹ️  Леммы выводятся в нормальной форме")
    print("ℹ️  Контексты показываются в оригинальном виде")
    print("=" * 60)

    documents = show_documents_list()

    if not documents:
        return

    while True:
        try:
            doc_id = input(f"\n👉 Введите ID документа: ").strip()
            doc_id = int(doc_id)

            doc_exists = False
            has_lemmas = False
            for doc in documents:
                if doc[0] == doc_id:
                    doc_exists = True
                    has_lemmas = doc[3]
                    break

            if doc_exists:
                if not has_lemmas:
                    print(f"⚠️ Для документа ID {doc_id} нет лемматизированной версии")
                    print("   Сначала запустите скрипт для лемматизации документов")
                    continue
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
            top_n = input("\n👉 Введите количество униграмм для вывода (по умолчанию 20): ").strip()
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

    get_top_unigrams_in_document(doc_id, top_n)


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА УНИГРАММ (на основе лемматизированных документов)")
    print("=" * 60)
    print("\nВыберите режим работы:")
    print("1 - Поиск по конкретному слову во всех документах")
    print("2 - Вывести топ-N униграмм по конкретному документу")

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