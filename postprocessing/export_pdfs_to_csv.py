# postprocessing/export_pdfs_to_csv.py
"""
Экспорт всех PDF документов в CSV файл
Сохраняет все поля таблицы documents для PDF файлов
"""

import sys
import csv
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2

try:
    from postprocessing.config import DATABASE_DSN
except ImportError:
    from config import DATABASE_DSN


def get_pdf_columns(conn):
    """Получает список всех колонок таблицы documents"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'documents' 
        ORDER BY ordinal_position
    """)
    columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return columns


def export_pdfs_to_csv(output_path=None, limit=None, include_content=True):
    """
    Экспортирует все PDF документы в CSV файл

    Args:
        output_path: Путь для сохранения CSV (если None - создаст в папке exports)
        limit: Ограничить количество PDF (для теста)
        include_content: Включать ли поле content (может быть очень большим)
    """
    print("=" * 70)
    print("📄 ЭКСПОРТ PDF ДОКУМЕНТОВ В CSV")
    print("=" * 70)

    # Подключаемся к БД
    try:
        conn = psycopg2.connect(DATABASE_DSN)
        print("✅ Подключение к PostgreSQL установлено")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return

    # Создаём папку для экспорта
    if output_path is None:
        exports_dir = Path(__file__).parent.parent / "exports"
        exports_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = exports_dir / f"pdf_export_{timestamp}.csv"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)

    # Получаем список колонок
    all_columns = get_pdf_columns(conn)

    # Если exclude_content, убираем поле content
    if not include_content and 'content' in all_columns:
        export_columns = [col for col in all_columns if col != 'content']
    else:
        export_columns = all_columns

    # Строим запрос
    query = f"""
        SELECT {', '.join(export_columns)}
        FROM documents 
        WHERE type = 'pdf'
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"

    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("❌ PDF документы не найдены!")
        conn.close()
        return

    print(f"\n📊 СТАТИСТИКА:")
    print(f"   📄 Найдено PDF: {len(rows)}")
    print(f"   📋 Колонок: {len(export_columns)}")
    print(f"   💾 Путь: {output_path}")

    # Записываем CSV
    print(f"\n🔄 Запись CSV...")

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile, delimiter=';', quoting=csv.QUOTE_MINIMAL)

        # Заголовки
        writer.writerow(export_columns)

        # Данные
        for row in rows:
            # Обрабатываем None и длинные тексты
            processed_row = []
            for value in row:
                if value is None:
                    processed_row.append('')
                elif isinstance(value, str) and len(value) > 500 and not include_content:
                    # Если поле content и мы его исключили - не попадает сюда
                    processed_row.append(value[:500] + '...')
                else:
                    processed_row.append(value)
            writer.writerow(processed_row)

    # Получаем размер файла
    file_size = output_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)

    cursor.close()
    conn.close()

    print(f"\n✅ ЭКСПОРТ ЗАВЕРШЁН!")
    print(f"   📄 Документов: {len(rows)}")
    print(f"   📋 Колонок: {len(export_columns)}")
    print(f"   💾 Размер файла: {file_size_mb:.2f} MB")
    print(f"   📁 Файл: {output_path}")
    print("=" * 70)

    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Экспорт PDF документов в CSV')
    parser.add_argument('--output', '-o', type=str, help='Путь для сохранения CSV')
    parser.add_argument('--limit', '-l', type=int, help='Ограничить количество PDF')
    parser.add_argument('--no-content', action='store_true', help='Не включать поле content')

    args = parser.parse_args()

    export_pdfs_to_csv(
        output_path=args.output,
        limit=args.limit,
        include_content=not args.no_content
    )


if __name__ == "__main__":
    main()