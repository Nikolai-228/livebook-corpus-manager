"""
Импорт данных из CSV файла обратно в таблицу documents
Обновляет content для PDF документов на основе ID
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
    """Импортирует данные из CSV в таблицу documents"""

    # Используем путь по умолчанию, если не указан
    if csv_path is None:
        csv_path = DEFAULT_CSV_PATH

    csv_path = Path(csv_path)

    print("=" * 70)
    print("📥 ИМПОРТ ДАННЫХ ИЗ CSV В ТАБЛИЦУ DOCUMENTS")
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
        has_id = 'id' in headers
        has_content = 'content' in headers


        if not has_id:
            print("❌ В CSV нет колонки 'id' - невозможно определить, какие документы обновлять")
            conn.close()
            return

        if not has_content:
            print("❌ В CSV нет колонок 'content' или 'title' - нечего обновлять")
            conn.close()
            return

        print(f"\n📋 Обнаружены колонки:")
        print(f"   ID: {'✅' if has_id else '❌'}")
        print(f"   content: {'✅' if has_content else '❌'}")


        # Читаем все строки
        rows = list(reader)

        # Получаем индексы
        id_idx = headers.index('id')
        content_idx = headers.index('content') if has_content else -1


        print(f"\n📊 Найдено строк: {len(rows)}")

    if dry_run:
        # Показываем первые 5 строк для примера
        print("\n📋 ПРИМЕРЫ ДАННЫХ ДЛЯ ИМПОРТА (первые 5):")
        print("-" * 70)
        for i, row in enumerate(rows[:5]):
            doc_id = row[id_idx]
            content_preview = row[content_idx][:100] + "..." if has_content and len(row[content_idx]) > 100 else row[
                content_idx] if has_content else "N/A"

            print(f"   ID: {doc_id}")
            if has_content:
                print(f"   content: {content_preview}")


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
                doc_id = int(row[id_idx])

                # Проверяем, существует ли документ
                cursor.execute("SELECT id FROM documents WHERE id = %s", (doc_id,))
                if not cursor.fetchone():
                    stats['not_found'] += 1
                    pbar.update(1)
                    continue

                # Обновляем content
                if update_content and has_content and content_idx != -1:
                    new_content = row[content_idx]
                    if new_content and new_content != '':
                        cursor.execute("""
                            UPDATE documents SET content = %s WHERE id = %s
                        """, (new_content, doc_id))
                        stats['updated_content'] += 1



                # Периодический коммит
                if (stats['updated_content'] + stats['updated_title']) % 100 == 0:
                    conn.commit()

            except Exception as e:
                stats['errors'] += 1
                print(f"\n❌ Ошибка при обработке ID {doc_id}: {e}")

            pbar.update(1)
            pbar.set_postfix({
                'content': stats['updated_content'],
                'title': stats['updated_title'],
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
    parser = argparse.ArgumentParser(description='Импорт данных из CSV в БД')

    # Делаем csv_file необязательным (nargs='?') и задаем значение по умолчанию
    parser.add_argument(
        'csv_file',
        type=str,
        nargs='?',  # <-- ВОПРОСИТЕЛЬНЫЙ ЗНАК делает аргумент необязательным
        default=DEFAULT_CSV_PATH,  # <-- Ваша константа
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