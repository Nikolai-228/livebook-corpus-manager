import psycopg2
import re
from collections import defaultdict, Counter

DB_CONFIG = {
    'host': 'livebook-team.duckdns.org',
    'port': 5432,
    'user': 'team_user',
    'password': 'book_live',
    'database': 'livebook_corpus'
}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


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


def get_all_documents_with_lemmas():
    """Получает все документы с лемматизированным текстом"""
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


def show_documents_for_search():
    """Показывает список документов для выбора с возможностью фильтрации"""
    print(f"\n{'=' * 70}")
    print("📚 ВЫБОР ДОКУМЕНТА ДЛЯ ПОИСКА")
    print(f"{'=' * 70}")

    documents = get_all_documents()
    if not documents:
        print("❌ Нет документов")
        return []

    # Спрашиваем фильтр
    filter_text = input("\n👉 Введите текст для фильтрации названий (Enter для вывода всех): ").strip()

    filtered_docs = []
    if filter_text:
        for doc_id, title, doc_type, _ in documents:
            if filter_text.lower() in (title or "").lower():
                filtered_docs.append((doc_id, title, doc_type))
    else:
        for doc_id, title, doc_type, _ in documents:
            filtered_docs.append((doc_id, title, doc_type))

    if not filtered_docs:
        print(f"\n❌ Документы с фильтром '{filter_text}' не найдены")
        return []

    print(f"\n📊 Найдено документов: {len(filtered_docs)}")
    print(f"{'─' * 70}")

    # Выводим в формате таблицы
    print(f"{'ID':<6} {'Тип':<15} {'Название'}")
    print(f"{'─' * 70}")

    for doc_id, title, doc_type in filtered_docs:
        title_short = title[:55] if title else "Без названия"
        doc_type_short = doc_type[:15] if doc_type else "Не указан"
        print(f"{doc_id:<6} {doc_type_short:<15} {title_short}")

    print(f"\n📊 Статистика по типам документов:")
    type_stats = Counter(doc[2] for doc in filtered_docs)
    for doc_type, count in type_stats.most_common():
        print(f"   {doc_type}: {count} документов")

    return filtered_docs


def search_by_regex(pattern: str, case_sensitive: bool = False, use_lemma: bool = False):
    """
    Поиск по регулярному выражению во всех документах

    Аргументы:
    - pattern: регулярное выражение для поиска
    - case_sensitive: учитывать регистр (по умолчанию False)
    - use_lemma: использовать лемматизированные тексты (по умолчанию False)
    """
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ПО РЕГУЛЯРНОМУ ВЫРАЖЕНИЮ")
    print(f"{'=' * 70}")
    print(f"📝 Шаблон: {pattern}")
    print(f"   Регистр: {'учтён' if case_sensitive else 'не учтён'}")
    print(f"   Текст: {'лемматизированный' if use_lemma else 'оригинальный'}")
    print(f"{'=' * 70}")

    conn = connect_db()

    try:
        # Выбираем таблицу для поиска
        if use_lemma:
            query = """
                SELECT d.id, d.title, d.type, dl.content
                FROM documents d
                INNER JOIN documents_lemmatized dl ON d.id = dl.id_documents
                WHERE dl.content IS NOT NULL AND dl.content != ''
                ORDER BY d.id
            """
        else:
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

        # Компилируем регулярное выражение
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
            if use_lemma:
                doc_id, title, doc_type, content = doc
            else:
                doc_id, title, doc_type, content = doc

            if not content:
                continue

            # Ищем все совпадения
            matches = []
            for match in regex.finditer(content):
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
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

        # Сортируем по количеству совпадений
        results.sort(key=lambda x: x['count'], reverse=True)

        # Вывод результатов
        print(f"\n✅ Найдено документов с совпадениями: {len(results)}")
        print(f"✅ Всего совпадений: {sum(r['count'] for r in results)}")

        if not results:
            print("\n❌ Совпадений не найдено")
            return

        print(f"\n{'=' * 70}")
        print(f"📊 РЕЗУЛЬТАТЫ ПОИСКА:")
        print(f"{'=' * 70}")

        for i, result in enumerate(results[:50], 1):  # Показываем топ-50 документов
            print(f"\n{i:2d}. 📄 Документ ID: {result['id']}")
            print(f"    Название: {result['title']}")
            print(f"    Тип: {result['type']}")
            print(f"    Совпадений: {result['count']}")

            # Показываем первые 5 совпадений
            for j, match in enumerate(result['matches'][:5], 1):
                # Подсвечиваем совпадение
                highlighted = match['context'].replace(
                    match['match'],
                    f"***{match['match']}***"
                )
                print(f"    {j}. ...{highlighted}...")

            if result['count'] > 5:
                print(f"    ... и еще {result['count'] - 5} совпадений")

        if len(results) > 50:
            print(f"\n... и еще {len(results) - 50} документов с совпадениями")

        # Статистика по типам документов
        type_stats = Counter(r['type'] for r in results)
        print(f"\n📈 СТАТИСТИКА ПО ТИПАМ ДОКУМЕНТОВ:")
        for doc_type, count in type_stats.most_common():
            print(f"   {doc_type}: {count} документов")

        # Статистика по частоте совпадений
        freq_stats = Counter(r['count'] for r in results)
        print(f"\n📈 СТАТИСТИКА ПО КОЛИЧЕСТВУ СОВПАДЕНИЙ:")
        for freq, count in sorted(freq_stats.items(), reverse=True)[:10]:
            print(f"   {freq} совпадений: {count} документов")

    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")
    finally:
        conn.close()


def search_in_document(doc_id: int, pattern: str, case_sensitive: bool = False, use_lemma: bool = False):
    """
    Поиск по регулярному выражению в конкретном документе

    Аргументы:
    - doc_id: ID документа
    - pattern: регулярное выражение для поиска
    - case_sensitive: учитывать регистр (по умолчанию False)
    - use_lemma: использовать лемматизированный текст (по умолчанию False)
    """
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК В ДОКУМЕНТЕ ПО РЕГУЛЯРНОМУ ВЫРАЖЕНИЮ")
    print(f"{'=' * 70}")
    print(f"📄 Документ ID: {doc_id}")
    print(f"📝 Шаблон: {pattern}")
    print(f"   Регистр: {'учтён' if case_sensitive else 'не учтён'}")
    print(f"   Текст: {'лемматизированный' if use_lemma else 'оригинальный'}")
    print(f"{'=' * 70}")

    conn = connect_db()

    try:
        # Получаем документ
        if use_lemma:
            query = """
                SELECT d.id, d.title, d.type, dl.content
                FROM documents d
                INNER JOIN documents_lemmatized dl ON d.id = dl.id_documents
                WHERE d.id = %s
            """
        else:
            query = """
                SELECT id, title, type, content
                FROM documents 
                WHERE id = %s
            """

        with conn.cursor() as cur:
            cur.execute(query, (doc_id,))
            result = cur.fetchone()

        if not result:
            print("❌ Документ не найден")
            return

        if use_lemma:
            doc_id, title, doc_type, content = result
        else:
            doc_id, title, doc_type, content = result

        if not content:
            print("❌ Документ пуст")
            return

        print(f"\n📄 Информация о документе:")
        print(f"   ID: {doc_id}")
        print(f"   Название: {title[:150] if title else 'Без названия'}")
        print(f"   Тип: {doc_type if doc_type else 'Не указан'}")
        print(f"   Размер текста: {len(content)} символов")

        # Компилируем регулярное выражение
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            print(f"❌ Ошибка в регулярном выражении: {e}")
            return

        # Ищем все совпадения
        matches = []
        for match in regex.finditer(content):
            start = max(0, match.start() - 70)
            end = min(len(content), match.end() + 70)
            context = content[start:end].replace('\n', ' ')
            matches.append({
                'match': match.group(),
                'start': match.start(),
                'end': match.end(),
                'context': context,
                'full_context': content[max(0, match.start() - 150):min(len(content), match.end() + 150)].replace('\n',
                                                                                                                  ' ')
            })

        if not matches:
            print("\n❌ Совпадений не найдено")
            return

        print(f"\n✅ Найдено совпадений: {len(matches)}")
        print(f"{'─' * 70}")

        # Выводим результаты
        for i, match in enumerate(matches, 1):
            print(f"\n{i:2d}. Совпадение: \"{match['match']}\"")
            print(f"    Позиция: {match['start']} - {match['end']}")

            # Подсвечиваем совпадение в контексте
            highlighted = match['context'].replace(
                match['match'],
                f"***{match['match']}***"
            )
            print(f"    Контекст: ...{highlighted}...")

        # Статистика
        match_counter = Counter(m['match'] for m in matches)
        print(f"\n📈 СТАТИСТИКА ПО СОВПАДЕНИЯМ:")
        print(f"   Всего совпадений: {len(matches)}")
        print(f"   Уникальных совпадений: {len(match_counter)}")
        print(f"   Топ-10 наиболее частых совпадений:")
        for word, count in match_counter.most_common(10):
            print(f"     - {word}: {count} раз(а)")

        # Позиции совпадений
        positions = [m['start'] for m in matches]
        if positions:
            print(f"\n📊 РАСПРЕДЕЛЕНИЕ ПО ТЕКСТУ:")
            print(f"   Первое совпадение: {positions[0]}")
            print(f"   Последнее совпадение: {positions[-1]}")
            print(
                f"   Средний интервал: {sum(positions[i + 1] - positions[i] for i in range(len(positions) - 1)) / max(1, len(positions) - 1):.0f} символов")

    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")
    finally:
        conn.close()


def search_by_mask_with_examples():
    """Поиск по маске с примерами популярных регулярных выражений"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ПОИСК ПО МАСКЕ С ПРИМЕРАМИ")
    print(f"{'=' * 70}")

    print("\n📌 ПРИМЕРЫ РЕГУЛЯРНЫХ ВЫРАЖЕНИЙ:")
    print(f"{'─' * 70}")

    examples = [
        {
            'name': 'Имена (Иван Петров)',
            'pattern': r'[А-Я][а-я]+\s+[А-Я][а-я]+',
            'description': 'Два слова с заглавной буквы подряд'
        },
        {
            'name': 'Имена с отчеством (Иван Иванович Петров)',
            'pattern': r'[А-Я][а-я]+\s+[А-Я][а-я]+\s+[А-Я][а-я]+',
            'description': 'Три слова с заглавной буквы подряд'
        },
        {
            'name': 'Инициалы (И.И. Иванов)',
            'pattern': r'[А-Я]\.\s*[А-Я]\.\s*[А-Я][а-я]+',
            'description': 'Инициалы и фамилия'
        },
        {
            'name': 'Названия организаций (ООО "Ромашка")',
            'pattern': r'(?:ООО|ЗАО|ОАО|ПАО)\s+["«]?[А-Я][а-я]+["»]?',
            'description': 'Организации с аббревиатурой'
        },
        {
            'name': 'Названия институтов (Ижевский механический институт)',
            'pattern': r'[А-Я][а-я]+(?:ский|ской)\s+[А-Я][а-я]+\s+(?:институт|университет|академия)',
            'description': 'Названия учебных заведений'
        },
        {
            'name': 'Годы (2024 год)',
            'pattern': r'\d{4}\s+год(?:а)?',
            'description': 'Год'
        },
        {
            'name': 'Даты (01.01.2024)',
            'pattern': r'\d{2}\.\d{2}\.\d{4}',
            'description': 'Дата в формате ДД.ММ.ГГГГ'
        },
        {
            'name': 'Телефоны (8-912-345-67-89)',
            'pattern': r'8[\- ]?\d{3}[\- ]?\d{3}[\- ]?\d{2}[\- ]?\d{2}',
            'description': 'Российский номер телефона'
        },
        {
            'name': 'Email (user@example.com)',
            'pattern': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'description': 'Электронная почта'
        },
        {
            'name': 'Сайты (http://example.com)',
            'pattern': r'https?://[^\s]+',
            'description': 'URL адрес'
        },
        {
            'name': 'Деньги (1000 рублей)',
            'pattern': r'\d+[\.,]?\d*\s*(?:руб|рублей?|₽)',
            'description': 'Денежные суммы в рублях'
        },
        {
            'name': 'Проценты (25%)',
            'pattern': r'\d+[\.,]?\d*\s*%',
            'description': 'Проценты'
        }
    ]

    for i, example in enumerate(examples, 1):
        print(f"\n{i:2d}. {example['name']}:")
        print(f"    Шаблон: {example['pattern']}")
        print(f"    Описание: {example['description']}")

    print(f"\n{'─' * 70}")
    print("\n💡 СОВЕТЫ ПО СОСТАВЛЕНИЮ РЕГУЛЯРНЫХ ВЫРАЖЕНИЙ:")
    print("   \\d  - любая цифра")
    print("   \\w  - любая буква или цифра")
    print("   \\s  - пробел")
    print("   [А-Я] - любая заглавная русская буква")
    print("   [а-я] - любая строчная русская буква")
    print("   +    - одно или более повторений")
    print("   *    - ноль или более повторений")
    print("   {n}  - ровно n повторений")
    print("   {n,m}- от n до m повторений")
    print("   ?    - ноль или одно повторение")
    print("   |    - логическое ИЛИ")
    print("   ()   - группа")
    print("   []   - класс символов")
    print("   ^    - начало строки")
    print("   $    - конец строки")
    print("   .    - любой символ (кроме перевода строки)")


def interactive_search():
    """Интерактивный режим для поиска по регулярному выражению"""
    print(f"\n{'=' * 60}")
    print("🔍 ПОИСК ПО РЕГУЛЯРНОМУ ВЫРАЖЕНИЮ")
    print(f"{'=' * 60}")

    print("\nВыберите режим работы:")
    print("1 - Поиск во всех документах")
    print("2 - Поиск в конкретном документе")
    print("3 - Показать примеры регулярных выражений")

    choice = input("\n👉 Ваш выбор (1/2/3): ").strip()

    if choice == '1':
        pattern = input("\n👉 Введите регулярное выражение: ").strip()
        if not pattern:
            print("❌ Шаблон не может быть пустым!")
            return

        case_sensitive = input("👉 Учитывать регистр? (y/n, по умолчанию n): ").strip().lower() == 'y'
        use_lemma = input("👉 Использовать лемматизированный текст? (y/n, по умолчанию n): ").strip().lower() == 'y'

        search_by_regex(pattern, case_sensitive, use_lemma)

    elif choice == '2':
        # Показываем список документов для выбора
        filtered_docs = show_documents_for_search()
        if not filtered_docs:
            return

        while True:
            try:
                doc_id = input(f"\n👉 Введите ID документа: ").strip()
                doc_id = int(doc_id)

                # Проверяем, существует ли такой документ
                if any(doc[0] == doc_id for doc in filtered_docs):
                    break
                else:
                    print(f"❌ Документ с ID {doc_id} не найден в текущем списке. Попробуйте снова.")
            except ValueError:
                print("❌ Пожалуйста, введите корректный числовой ID")

        pattern = input("\n👉 Введите регулярное выражение: ").strip()
        if not pattern:
            print("❌ Шаблон не может быть пустым!")
            return

        case_sensitive = input("👉 Учитывать регистр? (y/n, по умолчанию n): ").strip().lower() == 'y'
        use_lemma = input("👉 Использовать лемматизированный текст? (y/n, по умолчанию n): ").strip().lower() == 'y'

        search_in_document(doc_id, pattern, case_sensitive, use_lemma)

    elif choice == '3':
        search_by_mask_with_examples()

    else:
        print("❌ Неверный выбор!")


if __name__ == "__main__":
    print("🔍 СИСТЕМА ПОИСКА ПО РЕГУЛЯРНОМУ ВЫРАЖЕНИЮ")
    print("=" * 60)
    interactive_search()