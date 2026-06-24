import psycopg2
import re
from collections import defaultdict, Counter
# Подключение к БД
from db_connection import connect_db, DB_CONFIG


def get_all_documents():
    """Получает все документы из БД"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d.id, d.title, d.type, d.content
                FROM documents d
                WHERE d.content IS NOT NULL AND d.content != ''
                ORDER BY d.id
            """)
            documents = cur.fetchall()
        return documents
    except Exception as e:
        print(f"Ошибка при получении документов: {e}")
        return []
    finally:
        conn.close()


def get_mask_explanation():
    """Возвращает пояснение по составлению масок"""
    return """
📖 ПОЯСНЕНИЕ ПО СОСТАВЛЕНИЮ МАСОК (РЕГУЛЯРНЫХ ВЫРАЖЕНИЙ)

1. 📝 ПОИСК ВСЕХ СЛОВОФОРМ:
   Чтобы найти все формы слова, используйте:
   - шаблон: институт\w*  - найдет "институт", "института", "институту" и т.д.
   - шаблон: работ\w+     - найдет "работа", "работы", "работник" и т.д.
   💡 Символ \w* означает "любое количество букв"

2. 🌱 ПОИСК ПО ОПРЕДЕЛЕННОМУ КОРНЮ:
   Чтобы найти слова с одним корнем, используйте:
   - шаблон: студ\w+  - найдет "студент", "студенческий", "студенты"
   - шаблон: инженер\w* - найдет "инженер", "инженера", "инженерный"
   💡 Корень + \w+ (одна или более букв) находит все однокоренные слова

3. 🔚 ВЫБОР ОКОНЧАНИЯ:
   Один символ в окончании: 
   - шаблон: работ\w    - найдет "работа", "работы", "работу"
   - шаблон: студент\w  - найдет "студента", "студенту"

   Несколько символов в окончании:
   - шаблон: институт\w{3} - найдет слова с 3 буквами в окончании
   - шаблон: завод\w{2,4}  - найдет слова с 2-4 буквами в окончании
   💡 \w{3} - ровно 3 буквы, \w{2,4} - от 2 до 4 букв

4. 📌 ПОЛЕЗНЫЕ СИМВОЛЫ:
   • \d - любая цифра (0-9)
   • \w - любая буква (русская или английская)
   • \s - пробел
   • . - любой символ
   • + - одно или более повторений
   • * - ноль или более повторений
   • ? - ноль или одно повторение
   • {n} - ровно n повторений
   • {n,m} - от n до m повторений
   • | - логическое ИЛИ
   • () - группа
   • [] - класс символов
   • ^ - начало строки
   • $ - конец строки

5. 💡 ПРИМЕРЫ ДЛЯ ПОИСКА В ТЕКСТЕ:
   • Найти все годы: \d{4}\s+год
   • Найти все имена: [А-Я][а-я]+\s+[А-Я][а-я]+
   • Найти email: [a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
   • Найти телефон: 8[\- ]?\d{3}[\- ]?\d{3}[\- ]?\d{2}[\- ]?\d{2}
   • Найти организацию: (?:ООО|ЗАО|ОАО|ПАО)\s+["«]?[А-Я][а-я]+["»]?
   • Найти все слова с корнем "институт": институт\w*
   • Найти все формы слова "работа": работ\w+
   • Найти слова с окончанием из 2-3 букв: слово\w{2,3}

6. ⚠️ ВАЖНО:
   • Регистр имеет значение - используйте [А-Я] для заглавных и [а-я] для строчных
   • Для поиска точной фразы используйте пробелы между словами
   • Для поиска с учетом регистра включите соответствующую опцию
"""


def search_by_regex(pattern: str, case_sensitive: bool = False):
    """
    Поиск по регулярному выражению во всех документах (только оригинальный текст)
    """
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ПО РЕГУЛЯРНОМУ ВЫРАЖЕНИЮ")
    print(f"{'=' * 70}")
    print(f"📝 Шаблон: {pattern}")
    print(f"   Регистр: {'учтён' if case_sensitive else 'не учтён'}")
    print(f"   Текст: оригинальный")
    print(f"{'=' * 70}")

    conn = connect_db()
    try:
        query = """
            SELECT id, title, type, content
            FROM documents 
            WHERE content IS NOT NULL AND content != ''
            ORDER BY id
        """

        with conn.cursor() as cur:
            cur.execute(query)
            documents = cur.fetchall()

        if not documents:
            print("❌ Нет документов для поиска")
            return

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            print(f"❌ Ошибка в регулярном выражении: {e}")
            return

        results = []

        print(f"\n📊 Поиск в {len(documents)} документах...")
        print(f"{'─' * 70}")

        for doc in documents:
            doc_id, title, doc_type, content = doc

            if not content:
                continue

            matches = []
            for match in regex.finditer(content):
                start = max(0, match.start() - 70)
                end = min(len(content), match.end() + 70)
                context = content[start:end].replace('\n', ' ')
                matches.append({
                    'match': match.group(),
                    'start': match.start(),
                    'end': match.end(),
                    'context': context
                })

            if matches:
                results.append({
                    'id': doc_id,
                    'title': title[:100] if title else "Без названия",
                    'type': doc_type if doc_type else "Не указан",
                    'matches': matches,
                    'count': len(matches)
                })

        results.sort(key=lambda x: x['count'], reverse=True)

        print(f"\n✅ Найдено документов с совпадениями: {len(results)}")
        print(f"✅ Всего совпадений: {sum(r['count'] for r in results)}")

        if not results:
            print("\n❌ Совпадений не найдено")
            return

        print(f"\n{'=' * 70}")
        print(f"📊 РЕЗУЛЬТАТЫ ПОИСКА:")
        print(f"{'=' * 70}")

        for i, result in enumerate(results[:50], 1):
            print(f"\n{i:2d}. 📄 Документ ID: {result['id']}")
            print(f"    Название: {result['title']}")
            print(f"    Тип: {result['type']}")
            print(f"    Совпадений: {result['count']}")

            # Показываем все совпадения без звездочек
            for j, match in enumerate(result['matches'][:5], 1):
                print(f"    {j}. ...{match['context']}...")

            if result['count'] > 5:
                print(f"    ... и еще {result['count'] - 5} совпадений")

        if len(results) > 50:
            print(f"\n... и еще {len(results) - 50} документов с совпадениями")

        type_stats = Counter(r['type'] for r in results)
        print(f"\n📈 СТАТИСТИКА ПО ТИПАМ ДОКУМЕНТОВ:")
        for doc_type, count in type_stats.most_common():
            print(f"   {doc_type}: {count} документов")

        freq_stats = Counter(r['count'] for r in results)
        print(f"\n📈 СТАТИСТИКА ПО КОЛИЧЕСТВУ СОВПАДЕНИЙ:")
        for freq, count in sorted(freq_stats.items(), reverse=True)[:10]:
            print(f"   {freq} совпадений: {count} документов")

    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")
    finally:
        conn.close()


def show_examples():
    """Показывает примеры с пояснениями"""
    print(get_mask_explanation())
    input("\n👉 Нажмите Enter для продолжения...")


def interactive_search():
    """Интерактивный режим для поиска по регулярному выражению"""
    print(f"\n{'=' * 60}")
    print("🔍 ПОИСК ПО РЕГУЛЯРНОМУ ВЫРАЖЕНИЮ")
    print(f"{'=' * 60}")
    print("ℹ️  Поиск выполняется только по оригинальному тексту")
    print("=" * 60)

    print("\nВыберите режим работы:")
    print("1 - Поиск во всех документах")
    print("2 - Показать примеры и пояснения по маскам")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        pattern = input("\n👉 Введите регулярное выражение: ").strip()
        if not pattern:
            print("❌ Шаблон не может быть пустым!")
            return

        print("\n🔧 Настройки поиска:")
        case_sensitive = input("👉 Учитывать регистр? (y/n, по умолчанию n): ").strip().lower() == 'y'

        search_by_regex(pattern, case_sensitive)

    elif choice == '2':
        show_examples()

    else:
        print("❌ Неверный выбор!")


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА ПО РЕГУЛЯРНОМУ ВЫРАЖЕНИЮ")
    print("=" * 60)
    interactive_search()