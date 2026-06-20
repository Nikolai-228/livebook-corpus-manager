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


def get_lemmatized_tokens(doc_id: int):
    """Получает лемматизированный текст в виде списка токенов"""
    lemmatized_text = get_lemmatized_text(doc_id)
    if not lemmatized_text:
        return []

    # Разбиваем текст на токены (леммы уже разделены пробелами)
    tokens = lemmatized_text.lower().split()
    # Фильтруем стоп-слова и короткие слова
    tokens = [t for t in tokens if t not in RUSSIAN_STOP_WORDS and len(t) > 1]
    return tokens


def calculate_tf_ictf(doc_id: int, top_n: int = 30):
    """
    Вычисляет TF*ICTF для документа на основе лемматизированного текста
    TF (Term Frequency) - частота термина в документе
    ICTF (Inverse Collection Term Frequency) - обратная частота термина в коллекции
    """
    print(f"\n{'=' * 70}")
    print(f"📊 TF*ICTF ДЛЯ ДОКУМЕНТА ID: {doc_id}")
    print(f"{'=' * 70}")

    # Получаем информацию о документе
    doc_info = get_document_info(doc_id)
    if not doc_info:
        print("❌ Документ не найден")
        return

    # Получаем лемматизированный текст документа
    lemmatized_text = get_lemmatized_text(doc_id)
    if not lemmatized_text:
        print("❌ Для документа нет лемматизированной версии")
        return

    # Получаем все документы с лемматизированным текстом
    all_docs = get_all_documents_with_lemmas()
    if not all_docs:
        print("❌ Нет документов с лемматизированным текстом")
        return

    print(f"\n📄 Информация о документе:")
    print(f"   ID: {doc_id}")
    print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
    print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
    print(f"   Размер лемматизированного текста: {len(lemmatized_text)} символов")

    print(f"\n🔄 Обработка лемматизированных документов...")

    # Собираем все токены из всех документов
    all_tokens = []
    doc_tokens = {}

    for other_doc_id, title, doc_type, other_lemmatized_text in all_docs:
        if not other_lemmatized_text:
            continue
        tokens = other_lemmatized_text.lower().split()
        # Фильтруем стоп-слова и короткие слова
        tokens = [t for t in tokens if t not in RUSSIAN_STOP_WORDS and len(t) > 1]
        doc_tokens[other_doc_id] = tokens
        all_tokens.extend(tokens)

    # Токены текущего документа
    doc_tokens_current = doc_tokens.get(doc_id, [])

    # Вычисляем TF (частота в документе)
    tf = Counter(doc_tokens_current)

    # Вычисляем общую частоту всех слов в коллекции
    total_freq = Counter(all_tokens)
    total_tokens = len(all_tokens)

    # Вычисляем ICTF для каждого слова
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
        print(f"\n{i:2d}. Лемма: \"{token}\"")
        print(f"    TF*ICTF: {score:.4f}")
        print(f"    TF: {tf[token]}, ICTF: {ictf[token]:.4f}")
        print(f"    Частота в коллекции: {total_freq[token]}")

    # Статистика
    print(f"\n📈 СТАТИСТИКА:")
    print(f"   Всего уникальных лемм в документе: {len(tf)}")
    print(f"   Всего лемм в документе: {len(doc_tokens_current)}")
    print(f"   Всего лемм в коллекции: {total_tokens}")
    print(f"   Всего уникальных лемм в коллекции: {len(total_freq)}")


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
    """Интерактивный режим для выбора документа и расчета TF*ICTF"""
    print(f"\n{'=' * 60}")
    print("🔍 ПОИСК КЛЮЧЕВЫХ СЛОВ ПО TF*ICTF")
    print(f"{'=' * 60}")
    print("ℹ️  Используются лемматизированные тексты")
    print("=" * 60)

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

    # Вычисляем TF*ICTF
    calculate_tf_ictf(doc_id, top_n)


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА КЛЮЧЕВЫХ СЛОВ ПО TF*ICTF")
    print("=" * 60)
    interactive_search()