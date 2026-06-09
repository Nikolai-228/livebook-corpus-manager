# postprocessing/text_cleaner.py
"""
Единый модуль постобработки текстов и заголовков
Без нейросетей, без лишних полей, только регулярки
"""

import re
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from tqdm import tqdm

try:
    from postprocessing.config import DATABASE_DSN
except ImportError:
    from config import DATABASE_DSN

logger = logging.getLogger(__name__)


# ==========================================================
# 1. ОЧИСТКА ТЕКСТА (content)
# ==========================================================

def clean_text_basic(text):
    """Удаляет URL, сноски, номера страниц и лишние пробелы."""
    if not text:
        return ""

    # Удаляем URL
    text = re.sub(r'https?://\S+|www\.\S+', '', text, flags=re.IGNORECASE)

    # Удаляем сноски [1], (1), [*]
    text = re.sub(r'\[[0-9*]+\]|\([0-9*]+\)|\{[0-9*]+\}', '', text)

    # Удаляем номера страниц ("Страница 15", "15", "- 4 -")
    text = re.sub(r'\b(страница|с\.|page|p\.)\s*\d+\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+-\s*\d+\s*-\s+', ' ', text)

    # Нормализуем пробелы
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fix_pdf_text(text):
    """
    Специальная очистка для PDF: склеивает разорванные слова.
    Примеры: "конеч-\nно" -> "конечно", "сегод ня" -> "сегодня"
    """
    if not text:
        return ""

    # 1. Склеиваем слова, разорванные дефисом и переносом строки
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # 2. Склеиваем слова, разорванные пробелом и переносом строки
    text = re.sub(r'(\b[а-яa-z]{2,})\n(\w+\b)', r'\1\2', text, flags=re.IGNORECASE)

    # 3. Убираем лишние переносы строк внутри абзацев
    lines = text.split('\n')
    fixed_lines = []
    for line in lines:
        if fixed_lines and not fixed_lines[-1].rstrip().endswith(('.', '!', '?')):
            fixed_lines[-1] += ' ' + line.strip()
        else:
            fixed_lines.append(line.strip())

    final_text = ' '.join(fixed_lines)
    final_text = re.sub(r'\s+', ' ', final_text)

    return final_text.strip()


def postprocess_text(text, doc_type=None):
    """
    Главная функция для обработки текста.

    Args:
        text: Исходный текст
        doc_type: Тип документа ('pdf' или другое)

    Returns:
        Очищенный текст
    """
    if not text:
        return ""

    # Базовая очистка для всех типов
    cleaned = clean_text_basic(text)

    # Для PDF дополнительная очистка (склейка слов)
    if doc_type == 'pdf':
        cleaned = fix_pdf_text(cleaned)

    return cleaned


# ==========================================================
# 2. ОЧИСТКА НАЗВАНИЯ (title)
# ==========================================================

def clean_title(title, content):
    """
    Обрабатывает заголовок по правилам:
    1. Удаляет число в начале (1, 1.2, 1.2.3, 42,1)
    2. Делает первую букву заглавной
    3. Если content пустой или очень короткий - добавляет префикс "Документ с фотографиями"
    """
    if not title:
        title = "Без названия"

    original_title = title.strip()

    # Удаляем число в начале: цифры, точки, запятые, затем пробелы/дефисы/точки
    cleaned = re.sub(r'^[\d\,\.]+[\s\-\.]*', '', original_title)

    # Первая буква заглавная, остальные как есть
    if cleaned and len(cleaned) > 0:
        cleaned = cleaned[0].upper() + cleaned[1:]

    # Если после очистки пусто
    if not cleaned or cleaned.isspace():
        cleaned = "Без названия"

    # Проверяем, пустой ли content
    # content считается пустым, если: None, или пустая строка, или только пробелы, или очень короткий (< 50 символов)
    is_content_empty = (
            content is None or
            not content.strip() or
            len(content.strip()) < 50
    )

    # Если контента нет или он очень короткий (скорее всего фото), добавляем префикс
    if is_content_empty:
        return f'Документ с фотографиями "{cleaned}"'

    return cleaned


# ==========================================================
# 3. ЕДИНАЯ ФУНКЦИЯ ДЛЯ ОБРАБОТКИ БАЗЫ ДАННЫХ
# ==========================================================

def process_all_documents(limit=None, dry_run=False):
    """
    Обрабатывает ВСЕ документы в БД:
    - Очищает content (с учётом типа документа)
    - Очищает title (с учётом наличия content)
    - Сохраняет результаты прямо в те же поля (без лишних колонок)

    Args:
        limit: Ограничить количество документов
        dry_run: Только показать, что будет сделано
    """
    print("=" * 70)
    print("🚀 ПОСТОБРАБОТКА ВСЕХ ДОКУМЕНТОВ")
    print("   - Очистка content (PDF склеиваются)")
    print("   - Очистка title (удаление чисел, заглавная буква)")
    print("   - Документы с фото помечаются префиксом")
    print("=" * 70)

    if dry_run:
        print("⚠️ РЕЖИМ DRY RUN: изменения НЕ будут сохранены")

    # Подключаемся к БД
    try:
        conn = psycopg2.connect(DATABASE_DSN)
        print("✅ Подключение к PostgreSQL установлено")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return

    cursor = conn.cursor()

    # Получаем документы
    query = """
        SELECT id, title, content, type 
        FROM documents 
        WHERE content IS NOT NULL
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    documents = cursor.fetchall()

    print(f"\n📄 Найдено документов: {len(documents)}")

    # Статистика
    stats = {
        'total': len(documents),
        'content_changed': 0,
        'title_changed': 0,
        'photo_prefix_added': 0,
        'errors': 0
    }

    # Показываем примеры
    print("\n📋 ПРИМЕРЫ ОБРАБОТКИ (первые 5):")
    print("-" * 70)
    for doc_id, old_title, content, doc_type in documents[:5]:
        has_content = content is not None and len(content.strip()) > 50
        new_title = clean_title(old_title, content)
        prefix_marker = "📷" if not has_content else "📄"
        print(f"   {prefix_marker} ID: {doc_id} | Тип: {doc_type}")
        print(f"      Было: {old_title[:50] if old_title else 'None'}")
        print(f"      Стало: {new_title[:50]}")
        print()

    if dry_run:
        print("⚠️ DRY RUN: изменения не будут применены")
        conn.close()
        return

    # Обрабатываем документы
    print("\n🔄 Обработка...")

    with tqdm(total=stats['total'], desc="Обработка", unit="док") as pbar:
        for doc_id, old_title, content, doc_type in documents:
            try:
                # 1. Обрабатываем content
                new_content = postprocess_text(content, doc_type)

                # 2. Обрабатываем title
                new_title = clean_title(old_title, content)

                # Считаем изменения
                if new_content != content:
                    stats['content_changed'] += 1
                if new_title != old_title:
                    stats['title_changed'] += 1

                # Считаем добавленные префиксы
                if new_title != old_title and new_title.startswith('Документ с фотографиями'):
                    stats['photo_prefix_added'] += 1

                # 3. Обновляем БД
                cursor.execute("""
                    UPDATE documents 
                    SET content = %s, title = %s 
                    WHERE id = %s
                """, (new_content, new_title, doc_id))

                # Периодический коммит
                if stats['content_changed'] % 100 == 0 and stats['content_changed'] > 0:
                    conn.commit()

            except Exception as e:
                stats['errors'] += 1
                print(f"\n❌ Ошибка документа {doc_id}: {e}")

            pbar.update(1)
            pbar.set_postfix({
                'content': stats['content_changed'],
                'title': stats['title_changed'],
                '📷': stats['photo_prefix_added']
            })

    # Финальный коммит
    conn.commit()

    # Итоговая статистика
    print("\n" + "=" * 70)
    print("📊 СТАТИСТИКА ОБРАБОТКИ")
    print(f"   📄 Всего документов: {stats['total']}")
    print(f"   🔧 Изменено content: {stats['content_changed']}")
    print(f"   📝 Изменено title: {stats['title_changed']}")
    print(f"   📷 Добавлено 'Документ с фотографиями': {stats['photo_prefix_added']}")
    print(f"   ❌ Ошибок: {stats['errors']}")
    print("=" * 70)

    cursor.close()
    conn.close()
    print("\n✅ Обработка завершена!")


# ==========================================================
# 4. ТОЧКА ВХОДА
# ==========================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Постобработка документов')
    parser.add_argument('--limit', '-l', type=int, help='Ограничить количество')
    parser.add_argument('--dry-run', action='store_true', help='Пробный запуск без сохранения')

    args = parser.parse_args()

    process_all_documents(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()