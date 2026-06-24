"""
Импорт данных из CSV файла обратно в таблицу documents
Обновляет content для PDF документов на основе URL
"""

import sys
import csv
from pathlib import Path

# Укажите путь к CSV файлу здесь
DEFAULT_CSV_PATH = "D:\practica\livebook-corpus-manager\exports\pdf_deep.csv"

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from tqdm import tqdm

try:
    from postprocessing.config import DATABASE_DSN
except ImportError:
    from config import DATABASE_DSN


def import_csv_to_db(csv_path=None, dry_run=False, update_content=True, update_title=False):
    """Импортирует данные из CSV в таблицу documents по URL"""

    # Используем путь по умолчанию, если не указан
    if csv_path is None:
        csv_path = DEFAULT_CSV_PATH

    csv_path = Path(csv_path)

    print("=" * 70)
    print("📥 ИМПОРТ ДАННЫХ ИЗ CSV В ТАБЛИЦУ DOCUMENTS (ПО URL)")
    print("=" * 70)
    print(f"📄 Файл: {csv_path}")

    if dry_run:
        print("⚠️ РЕЖИМ DRY RUN: изменения НЕ будут сохранены")

    if not csv_path.exists():
        print(f"❌ Файл не найден: {csv_path}")
        return

    # Подключаемся к БД
    try:
        conn = psycopg2.connect(DATABASE_DSN)
        print("✅ Подключение к PostgreSQL установлено")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return

    cursor = conn.cursor()

    # Читаем CSV и получаем заголовки
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        headers = next(reader)

        # Проверяем, какие колонки есть в файле
        has_url = 'url' in headers
        has_content = 'content' in headers
        has_title = 'title' in headers

        if not has_url:
            print("❌ В CSV нет колонки 'url' - невозможно определить, какие документы обновлять")
            conn.close()
            return

        if not has_content and not has_title:
            print("❌ В CSV нет колонок 'content' или 'title' - нечего обновлять")
            conn.close()
            return

        print(f"\n📋 Обнаружены колонки:")
        print(f"   URL: {'✅' if has_url else '❌'}")
        print(f"   content: {'✅' if has_content else '❌'}")
        print(f"   title: {'✅' if has_title else '❌'}")

        # Читаем все строки
        rows = list(reader)

        # Получаем индексы
        url_idx = headers.index('url')
        content_idx = headers.index('content') if has_content else -1
        title_idx = headers.index('title') if has_title else -1

        print(f"\n📊 Найдено строк: {len(rows)}")

        # Проверяем, есть ли дубликаты URL
        urls = [row[url_idx] for row in rows if row[url_idx]]
        unique_urls = len(set(urls))
        if len(urls) != unique_urls:
            print(f"⚠️ ВНИМАНИЕ: Обнаружено {len(urls) - unique_urls} дубликатов URL")

    if dry_run:
        # Показываем первые 5 строк для примера
        print("\n📋 ПРИМЕРЫ ДАННЫХ ДЛЯ ИМПОРТА (первые 5):")
        print("-" * 70)
        for i, row in enumerate(rows[:5]):
            url = row[url_idx]
            content_preview = row[content_idx][:100] + "..." if has_content and len(row[content_idx]) > 100 else row[content_idx] if has_content else "N/A"

            print(f"   URL: {url}")
            if has_content:
                print(f"   content: {content_preview}")
            if has_title:
                print(f"   title: {row[title_idx][:50]}")
            print()

        print("\n⚠️ DRY RUN: изменения не будут применены")
        print("   Убери флаг --dry-run для реального импорта")
        conn.close()
        return

    # Обновляем данные
    print("\n🔄 Импорт данных...")

    stats = {
        'total': len(rows),
        'updated_content': 0,
        'updated_title': 0,
        'errors': 0,
        'not_found': 0
    }

    with tqdm(total=stats['total'], desc="Импорт", unit="док") as pbar:
        for row in rows:
            try:
                url = row[url_idx]

                if not url:
                    stats['errors'] += 1
                    pbar.update(1)
                    continue

                # Проверяем, существует ли документ с таким URL
                cursor.execute("SELECT id FROM documents WHERE url = %s", (url,))
                result = cursor.fetchone()

                if not result:
                    stats['not_found'] += 1
                    pbar.update(1)
                    continue

                doc_id = result[0]

                # Собираем поля для обновления
                update_fields = []
                update_values = []

                # Обновляем content
                if update_content and has_content and content_idx != -1:
                    new_content = row[content_idx]
                    if new_content and new_content != '':
                        update_fields.append("content = %s")
                        update_values.append(new_content)
                        stats['updated_content'] += 1

                # Обновляем title
                if update_title and has_title and title_idx != -1:
                    new_title = row[title_idx]
                    if new_title and new_title != '':
                        update_fields.append("title = %s")
                        update_values.append(new_title)
                        stats['updated_title'] += 1

                # Если есть что обновлять
                if update_fields:
                    update_values.append(doc_id)
                    query = f"""
                        UPDATE documents 
                        SET {', '.join(update_fields)} 
                        WHERE id = %s
                    """
                    cursor.execute(query, tuple(update_values))

                # Периодический коммит
                if (stats['updated_content'] + stats['updated_title']) % 100 == 0:
                    conn.commit()

            except Exception as e:
                stats['errors'] += 1
                print(f"\n❌ Ошибка при обработке URL {url}: {e}")

            pbar.update(1)
            pbar.set_postfix({
                'content': stats['updated_content'],
                'title': stats['updated_title'],
                'не найдено': stats['not_found'],
                'ошибки': stats['errors']
            })

    # Финальный коммит
    conn.commit()

    # Статистика
    print("\n" + "=" * 70)
    print("📊 СТАТИСТИКА ИМПОРТА")
    print(f"   📄 Всего строк: {stats['total']}")
    print(f"   ✅ Обновлено content: {stats['updated_content']}")
    print(f"   ✅ Обновлено title: {stats['updated_title']}")
    print(f"   ❌ Документов не найдено: {stats['not_found']}")
    print(f"   ❌ Ошибок: {stats['errors']}")
    print("=" * 70)

    # Проверка результата
    cursor.execute("""
        SELECT COUNT(*) FROM documents WHERE type = 'pdf'
    """)
    total_pdfs = cursor.fetchone()[0]
    print(f"\n📊 Всего PDF в БД: {total_pdfs}")

    cursor.close()
    conn.close()

    print("\n✅ Импорт завершён!")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Импорт данных из CSV в БД по URL')

    parser.add_argument(
        'csv_file',
        type=str,
        nargs='?',
        default=DEFAULT_CSV_PATH,
        help='Путь к CSV файлу (по умолчанию: %(default)s)'
    )

    parser.add_argument('--dry-run', action='store_true', help='Пробный запуск без сохранения')
    parser.add_argument('--no-content', action='store_true', help='Не обновлять поле content')
    parser.add_argument('--update-title', action='store_true', help='Обновлять поле title')

    args = parser.parse_args()

    import_csv_to_db(
        csv_path=args.csv_file,
        dry_run=args.dry_run,
        update_content=not args.no_content,
        update_title=args.update_title
    )


if __name__ == "__main__":
    main()