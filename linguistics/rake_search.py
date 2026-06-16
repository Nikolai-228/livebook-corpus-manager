import psycopg2
import re
from nltk.corpus import stopwords
from pymorphy3 import MorphAnalyzer
from nltk.tokenize import word_tokenize
from collections import Counter
import math
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


def get_document_content(doc_id: int):
    """Получает содержимое документа"""
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


def get_all_documents_content():
    """Получает содержимое всех документов"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, content, type 
                FROM documents 
                WHERE content IS NOT NULL AND content != ''
                ORDER BY id
            """)
            documents = cur.fetchall()
        return documents
    except Exception as e:
        print(f"Ошибка при получении документов: {e}")
        return []
    finally:
        conn.close()


def preprocess_text(text: str, morph=None) -> list:
    """Предобработка текста: токенизация, очистка, лемматизация"""
    if not text:
        return []

    # Очистка текста
    text = re.sub(r'[^\w\s]', ' ', text.lower())

    # Токенизация
    tokens = word_tokenize(text, language='russian')

    # Фильтрация стоп-слов и коротких слов
    tokens = [t for t in tokens if t.isalpha() and t not in RUSSIAN_STOP_WORDS and len(t) > 1]

    # Лемматизация
    if morph:
        lemmatized = []
        for token in tokens:
            try:
                lemma = morph.parse(token)[0].normal_form
                if len(lemma) > 1:
                    lemmatized.append(lemma)
            except:
                lemmatized.append(token)
        return lemmatized

    return tokens


def calculate_tf_idf(doc_id: int, top_n: int = 30):
    """
    Вычисляет TF*IDF для документа
    TF (Term Frequency) - частота термина в документе
    IDF (Inverse Document Frequency) - обратная частота документа
    """
    print(f"\n{'=' * 70}")
    print(f"📊 TF*IDF ДЛЯ ДОКУМЕНТА ID: {doc_id}")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()

    # Получаем информацию о документе
    doc_info = get_document_content(doc_id)
    if not doc_info:
        print("❌ Документ не найден")
        return

    # Получаем все документы для расчета IDF
    all_docs = get_all_documents_content()
    if not all_docs:
        print("❌ Нет документов")
        return

    print(f"\n📄 Информация о документе:")
    print(f"   ID: {doc_id}")
    print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
    print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
    print(f"   Размер текста: {len(doc_info['content'])} символов")

    # Предобработка всех документов
    print(f"\n🔄 Обработка документов...")

    doc_tokens = {}
    all_tokens = []

    for doc_id_other, title, content, doc_type in all_docs:
        if not content:
            continue
        tokens = preprocess_text(content, morph)
        doc_tokens[doc_id_other] = tokens
        all_tokens.extend(tokens)

    # Вычисляем TF для текущего документа
    doc_tokens_current = doc_tokens.get(doc_id, [])
    tf = Counter(doc_tokens_current)

    # Вычисляем IDF для каждого слова
    N = len(doc_tokens)  # общее количество документов
    idf = {}
    for token in set(all_tokens):
        # Количество документов, содержащих слово
        doc_freq = sum(1 for tokens in doc_tokens.values() if token in tokens)
        if doc_freq > 0:
            idf[token] = math.log(N / doc_freq)
        else:
            idf[token] = 0

    # Вычисляем TF*IDF
    tf_idf_scores = {}
    for token, tf_value in tf.items():
        if token in idf:
            tf_idf_scores[token] = tf_value * idf[token]

    # Сортируем по убыванию
    sorted_scores = sorted(tf_idf_scores.items(), key=lambda x: x[1], reverse=True)

    print(f"\n📊 ТОП-{min(top_n, len(sorted_scores))} КЛЮЧЕВЫХ СЛОВ ПО TF*IDF:")
    print(f"{'─' * 70}")

    for i, (token, score) in enumerate(sorted_scores[:top_n], 1):
        # Находим контекст для слова
        contexts = []
        text_lower = doc_info['content'].lower()
        pos = 0
        while len(contexts) < 2:
            found = text_lower.find(token, pos)
            if found == -1:
                break
            start = max(0, found - 50)
            end = min(len(doc_info['content']), found + len(token) + 50)
            contexts.append(doc_info['content'][start:end].replace('\n', ' '))
            pos = found + 1

        print(f"\n{i:2d}. \"{token}\"")
        print(f"    TF*IDF: {score:.4f}")
        print(f"    TF: {tf[token]}, IDF: {idf[token]:.4f}")
        if contexts:
            ctx_clean = re.sub(r'\s+', ' ', contexts[0])
            print(f"    Контекст: ...{ctx_clean[:120]}...")

    # Статистика
    print(f"\n📈 СТАТИСТИКА:")
    print(f"   Всего уникальных слов в документе: {len(tf)}")
    print(f"   Всего слов в документе: {len(doc_tokens_current)}")
    print(f"   Всего документов в корпусе: {N}")


def calculate_tf_ictf(doc_id: int, top_n: int = 30):
    """
    Вычисляет TF*ICTF для документа
    TF (Term Frequency) - частота термина в документе
    ICTF (Inverse Collection Term Frequency) - обратная частота термина в коллекции
    """
    print(f"\n{'=' * 70}")
    print(f"📊 TF*ICTF ДЛЯ ДОКУМЕНТА ID: {doc_id}")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()

    # Получаем информацию о документе
    doc_info = get_document_content(doc_id)
    if not doc_info:
        print("❌ Документ не найден")
        return

    # Получаем все документы для расчета ICTF
    all_docs = get_all_documents_content()
    if not all_docs:
        print("❌ Нет документов")
        return

    print(f"\n📄 Информация о документе:")
    print(f"   ID: {doc_id}")
    print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
    print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
    print(f"   Размер текста: {len(doc_info['content'])} символов")

    # Предобработка всех документов
    print(f"\n🔄 Обработка документов...")

    doc_tokens = {}
    all_tokens = []

    for doc_id_other, title, content, doc_type in all_docs:
        if not content:
            continue
        tokens = preprocess_text(content, morph)
        doc_tokens[doc_id_other] = tokens
        all_tokens.extend(tokens)

    # Общая частота всех слов в коллекции
    total_freq = Counter(all_tokens)

    # Вычисляем TF для текущего документа
    doc_tokens_current = doc_tokens.get(doc_id, [])
    tf = Counter(doc_tokens_current)

    # Вычисляем ICTF для каждого слова
    total_tokens = len(all_tokens)
    ictf = {}
    for token in set(all_tokens):
        if total_tokens > 0 and total_freq[token] > 0:
            ictf[token] = math.log(total_tokens / total_freq[token])
        else:
            ictf[token] = 0

    # Вычисляем TF*ICTF
    tf_ictf_scores = {}
    for token, tf_value in tf.items():
        if token in ictf:
            tf_ictf_scores[token] = tf_value * ictf[token]

    # Сортируем по убыванию
    sorted_scores = sorted(tf_ictf_scores.items(), key=lambda x: x[1], reverse=True)

    print(f"\n📊 ТОП-{min(top_n, len(sorted_scores))} КЛЮЧЕВЫХ СЛОВ ПО TF*ICTF:")
    print(f"{'─' * 70}")

    for i, (token, score) in enumerate(sorted_scores[:top_n], 1):
        # Находим контекст для слова
        contexts = []
        text_lower = doc_info['content'].lower()
        pos = 0
        while len(contexts) < 2:
            found = text_lower.find(token, pos)
            if found == -1:
                break
            start = max(0, found - 50)
            end = min(len(doc_info['content']), found + len(token) + 50)
            contexts.append(doc_info['content'][start:end].replace('\n', ' '))
            pos = found + 1

        print(f"\n{i:2d}. \"{token}\"")
        print(f"    TF*ICTF: {score:.4f}")
        print(f"    TF: {tf[token]}, ICTF: {ictf[token]:.4f}")
        print(f"    Частота в коллекции: {total_freq[token]}")
        if contexts:
            ctx_clean = re.sub(r'\s+', ' ', contexts[0])
            print(f"    Контекст: ...{ctx_clean[:120]}...")

    # Статистика
    print(f"\n📈 СТАТИСТИКА:")
    print(f"   Всего уникальных слов в документе: {len(tf)}")
    print(f"   Всего слов в документе: {len(doc_tokens_current)}")
    print(f"   Всего слов в коллекции: {total_tokens}")
    print(f"   Всего уникальных слов в коллекции: {len(total_freq)}")


def show_documents_list():
    """Показывает список всех документов для выбора"""
    documents = get_all_documents()

    if not documents:
        print("❌ Нет доступных документов")
        return None

    print(f"\n{'=' * 70}")
    print("📚 СПИСОК ДОСТУПНЫХ ДОКУМЕНТОВ")
    print(f"{'=' * 70}")
    print(f"\n{'ID':<6} {'Тип':<12} {'Название'}")
    print(f"{'─' * 70}")

    for doc_id, title, doc_type in documents:
        title_short = title[:50] if title else "Без названия"
        doc_type_short = doc_type[:10] if doc_type else "Не указан"
        print(f"{doc_id:<6} {doc_type_short:<12} {title_short}")

    return documents


def interactive_search():
    """Интерактивный режим для выбора метрики и документа"""
    print(f"\n{'=' * 60}")
    print("🔍 ПОИСК КЛЮЧЕВЫХ СЛОВ ПО TF*IDF И TF*ICTF")
    print(f"{'=' * 60}")

    print("\nВыберите метрику:")
    print("1 - TF*IDF (Term Frequency - Inverse Document Frequency)")
    print("2 - TF*ICTF (Term Frequency - Inverse Collection Term Frequency)")

    metric_choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if metric_choice not in ['1', '2']:
        print("❌ Неверный выбор!")
        return

    # Показываем список документов
    documents = show_documents_list()

    if not documents:
        return

    # Выбор документа
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

    # Ввод количества ключевых слов
    while True:
        try:
            top_n = input("\n👉 Введите количество ключевых слов для вывода (по умолчанию 30): ").strip()
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

    # Вычисляем выбранную метрику
    if metric_choice == '1':
        calculate_tf_idf(doc_id, top_n)
    else:
        calculate_tf_ictf(doc_id, top_n)


def compare_metrics(doc_id: int, top_n: int = 20):
    """Сравнивает результаты TF*IDF и TF*ICTF для одного документа"""
    print(f"\n{'=' * 70}")
    print(f"📊 СРАВНЕНИЕ TF*IDF И TF*ICTF ДЛЯ ДОКУМЕНТА ID: {doc_id}")
    print(f"{'=' * 70}")

    morph = MorphAnalyzer()

    # Получаем информацию о документе
    doc_info = get_document_content(doc_id)
    if not doc_info:
        print("❌ Документ не найден")
        return

    # Получаем все документы
    all_docs = get_all_documents_content()
    if not all_docs:
        print("❌ Нет документов")
        return

    print(f"\n📄 Информация о документе:")
    print(f"   ID: {doc_id}")
    print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
    print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")

    # Предобработка всех документов
    print(f"\n🔄 Обработка документов...")

    doc_tokens = {}
    all_tokens = []

    for doc_id_other, title, content, doc_type in all_docs:
        if not content:
            continue
        tokens = preprocess_text(content, morph)
        doc_tokens[doc_id_other] = tokens
        all_tokens.extend(tokens)

    # Вычисляем TF для текущего документа
    doc_tokens_current = doc_tokens.get(doc_id, [])
    tf = Counter(doc_tokens_current)

    # Вычисляем IDF
    N = len(doc_tokens)
    idf = {}
    for token in set(all_tokens):
        doc_freq = sum(1 for tokens in doc_tokens.values() if token in tokens)
        if doc_freq > 0:
            idf[token] = math.log(N / doc_freq)
        else:
            idf[token] = 0

    # Вычисляем ICTF
    total_freq = Counter(all_tokens)
    total_tokens = len(all_tokens)
    ictf = {}
    for token in set(all_tokens):
        if total_tokens > 0 and total_freq[token] > 0:
            ictf[token] = math.log(total_tokens / total_freq[token])
        else:
            ictf[token] = 0

    # Вычисляем TF*IDF и TF*ICTF
    tf_idf_scores = {}
    tf_ictf_scores = {}
    for token, tf_value in tf.items():
        if token in idf:
            tf_idf_scores[token] = tf_value * idf[token]
        if token in ictf:
            tf_ictf_scores[token] = tf_value * ictf[token]

    # Сортируем
    tf_idf_sorted = sorted(tf_idf_scores.items(), key=lambda x: x[1], reverse=True)
    tf_ictf_sorted = sorted(tf_ictf_scores.items(), key=lambda x: x[1], reverse=True)

    print(f"\n📊 СРАВНЕНИЕ ТОП-{top_n} КЛЮЧЕВЫХ СЛОВ:")
    print(f"{'─' * 100}")
    print(f"{'#':<4} {'TF*IDF':<25} {'Score':<12} {'TF*ICTF':<25} {'Score':<12}")
    print(f"{'─' * 100}")

    for i in range(min(top_n, len(tf_idf_sorted), len(tf_ictf_sorted))):
        tf_idf_word, tf_idf_score = tf_idf_sorted[i] if i < len(tf_idf_sorted) else ("-", 0)
        tf_ictf_word, tf_ictf_score = tf_ictf_sorted[i] if i < len(tf_ictf_sorted) else ("-", 0)

        print(f"{i + 1:<4} {tf_idf_word:<25} {tf_idf_score:<12.4f} {tf_ictf_word:<25} {tf_ictf_score:<12.4f}")

    # Общие слова в топе
    tf_idf_top = set([word for word, _ in tf_idf_sorted[:top_n]])
    tf_ictf_top = set([word for word, _ in tf_ictf_sorted[:top_n]])
    common = tf_idf_top & tf_ictf_top

    print(f"\n📈 СТАТИСТИКА СРАВНЕНИЯ:")
    print(f"   Пересечение топ-{top_n}: {len(common)} слов")
    print(f"   Уникальные для TF*IDF: {len(tf_idf_top - tf_ictf_top)} слов")
    print(f"   Уникальные для TF*ICTF: {len(tf_ictf_top - tf_idf_top)} слов")

    if common:
        print(f"\n   Общие слова в топ-{top_n}:")
        for word in sorted(common)[:10]:
            print(f"     - {word}")


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА КЛЮЧЕВЫХ СЛОВ (TF*IDF и TF*ICTF)")
    print("=" * 60)
    print("\nВыберите действие:")
    print("1 - Вычислить ключевые слова для документа по одной метрике")
    print("2 - Сравнить TF*IDF и TF*ICTF для одного документа")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        interactive_search()
    elif choice == '2':
        # Показываем список документов
        documents = show_documents_list()
        if not documents:
            exit()

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
                exit()

        while True:
            try:
                top_n = input("\n👉 Введите количество ключевых слов для сравнения (по умолчанию 20): ").strip()
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

        compare_metrics(doc_id, top_n)
    else:
        print("❌ Неверный выбор! Запустите программу снова.")