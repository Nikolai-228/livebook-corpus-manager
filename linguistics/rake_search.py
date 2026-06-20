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
# Подключение к БД
from db_connection import connect_db, DB_CONFIG
RUSSIAN_STOP_WORDS = set(stopwords.words('russian'))

def get_documents_by_chapter(chapter_id: int):
    """Получает все документы из конкретного раздела с лемматизированным текстом"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.type, dl.content
                FROM documents d
                INNER JOIN documents_lemmatized dl ON d.id = dl.id_documents
                WHERE d.chapter_id = %s AND dl.content IS NOT NULL AND dl.content != ''
                ORDER BY d.id
            """, (chapter_id,))
            documents = cur.fetchall()
        return documents
    except Exception as e:
        print(f"Ошибка при получении документов раздела: {e}")
        return []
    finally:
        conn.close()


def get_all_chapters():
    """Получает список всех разделов"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name
                FROM chapters
                ORDER BY id
            """)
            chapters = cur.fetchall()
        return chapters
    except Exception as e:
        print(f"Ошибка при получении списка разделов: {e}")
        return []
    finally:
        conn.close()

def get_document_info(doc_id: int):
    """Получает информацию о документе (название, тип, chapter_id)"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT title, type, chapter_id
                FROM documents 
                WHERE id = %s
            """, (doc_id,))
            result = cur.fetchone()
            if result:
                return {
                    'title': result[0],
                    'type': result[1],
                    'chapter_id': result[2]
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

def calculate_tf_ictf(doc_id: int, top_n: int = 30):
    """
    Вычисляет TF*ICTF для документа на основе коллекции его раздела
    """
    print(f"\n{'=' * 70}")
    print(f"📊 TF*ICTF ДЛЯ ДОКУМЕНТА ID: {doc_id}")
    print(f"{'=' * 70}")

    # Получаем информацию о документе
    doc_info = get_document_info(doc_id)
    if not doc_info:
        print("❌ Документ не найден")
        return

    chapter_id = doc_info['chapter_id']
    if not chapter_id:
        print("❌ Документ не привязан ни к одному разделу")
        print("   Используйте документы, у которых заполнено поле chapter_id")
        return

    # Получаем лемматизированный текст документа
    lemmatized_text = get_lemmatized_text(doc_id)
    if not lemmatized_text:
        print("❌ Для документа нет лемматизированной версии")
        return

    # Получаем все документы из этого же раздела
    docs_in_chapter = get_documents_by_chapter(chapter_id)
    if not docs_in_chapter:
        print(f"❌ В разделе ID {chapter_id} нет документов с лемматизированным текстом")
        return

    print(f"\n📄 Информация о документе:")
    print(f"   ID: {doc_id}")
    print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
    print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
    print(f"   Раздел: ID {chapter_id}")
    print(f"   Размер лемматизированного текста: {len(lemmatized_text)} символов")

    print(f"\n🔄 Обработка лемматизированных документов раздела...")
    print(f"   Всего документов в разделе: {len(docs_in_chapter)}")

    # Собираем все токены из документов раздела
    all_tokens = []
    doc_tokens = {}

    for other_doc_id, title, doc_type, other_lemmatized_text in docs_in_chapter:
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

    # Вычисляем общую частоту всех слов в коллекции раздела
    total_freq = Counter(all_tokens)
    total_tokens = len(all_tokens)

    # Вычисляем ICTF для каждого слова (на основе коллекции раздела)
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
        print(f"    Частота в разделе: {total_freq[token]}")

    # Статистика
    print(f"\n📈 СТАТИСТИКА:")
    print(f"   Всего уникальных лемм в документе: {len(tf)}")
    print(f"   Всего лемм в документе: {len(doc_tokens_current)}")
    print(f"   Всего лемм в разделе: {total_tokens}")
    print(f"   Всего уникальных лемм в разделе: {len(total_freq)}")
    print(f"   Всего документов в разделе: {len(docs_in_chapter)}")


def show_chapters_list():
    """Показывает список всех разделов"""
    chapters = get_all_chapters()

    if not chapters:
        print("❌ Нет доступных разделов")
        return None

    print(f"\n{'=' * 70}")
    print("📚 СПИСОК РАЗДЕЛОВ")
    print(f"{'=' * 70}")
    print(f"\n{'ID':<6} {'Название'}")
    print(f"{'─' * 70}")

    for chapter_id, name in chapters:
        name_short = name[:60] if name else "Без названия"
        print(f"{chapter_id:<6} {name_short}")

    return chapters


def show_documents_by_chapter(chapter_id: int):
    """Показывает список документов в разделе"""
    documents = get_documents_by_chapter(chapter_id)

    if not documents:
        print(f"❌ В разделе ID {chapter_id} нет документов с лемматизированным текстом")
        return None

    print(f"\n{'=' * 70}")
    print(f"📚 ДОКУМЕНТЫ РАЗДЕЛА ID: {chapter_id}")
    print(f"{'=' * 70}")
    print(f"\n{'ID':<6} {'Тип':<12} {'Название'}")
    print(f"{'─' * 70}")

    for doc_id, title, doc_type, _ in documents:
        title_short = title[:50] if title else "Без названия"
        doc_type_short = doc_type[:10] if doc_type else "Не указан"
        print(f"{doc_id:<6} {doc_type_short:<12} {title_short}")

    print(f"\n📊 Всего документов в разделе: {len(documents)}")

    return documents


def interactive_search():
    """Интерактивный режим для выбора документа и расчета TF*ICTF"""
    print(f"\n{'=' * 60}")
    print("🔍 ПОИСК КЛЮЧЕВЫХ СЛОВ ПО TF*ICTF")
    print(f"{'=' * 60}")
    print("ℹ️  Используются лемматизированные тексты")
    print("ℹ️  Коллекция для расчета ICTF - документы одного раздела")
    print("=" * 60)

    # Показываем список разделов
    chapters = show_chapters_list()
    if not chapters:
        return

    # Выбор раздела
    while True:
        try:
            chapter_id = input(f"\n👉 Введите ID раздела: ").strip()
            chapter_id = int(chapter_id)

            chapter_exists = any(ch[0] == chapter_id for ch in chapters)
            if chapter_exists:
                break
            else:
                print(f"❌ Раздел с ID {chapter_id} не найден. Попробуйте снова.")
        except ValueError:
            print("❌ Пожалуйста, введите корректный числовой ID")
        except KeyboardInterrupt:
            print("\n👋 Отмена")
            return

    # Показываем документы раздела
    documents = show_documents_by_chapter(chapter_id)
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
                print(f"❌ Документ с ID {doc_id} не найден в этом разделе. Попробуйте снова.")
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