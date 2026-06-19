import psycopg2
import re
from collections import defaultdict

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
    """Получает список всех документов с биграммами"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT d.id, d.title, d.type, d.chapter_id
                FROM documents d
                INNER JOIN new_bigrams b ON d.id = b.id_documents
                WHERE d.content IS NOT NULL AND d.content != ''
                ORDER BY d.id
            """)
            return cur.fetchall()
    finally:
        conn.close()


def get_document_info(doc_id: int):
    """Получает информацию о документе"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, type, chapter_id
                FROM documents 
                WHERE id = %s
            """, (doc_id,))
            return cur.fetchone()
    finally:
        conn.close()


def get_chapters():
    """Получает список всех разделов"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name FROM chapters ORDER BY id
            """)
            return cur.fetchall()
    finally:
        conn.close()


def get_bigrams_for_document(doc_id: int):
    """
    Получает ВСЕ биграммы для конкретного документа
    Сортировка по частоте (от большего к меньшему)
    БЕЗ ограничений
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    bigram, 
                    word1, 
                    word2, 
                    frequency, 
                    contexts
                FROM new_bigrams
                WHERE id_documents = %s
                ORDER BY frequency DESC
            """, (doc_id,))
            return cur.fetchall()
    finally:
        conn.close()


def get_bigrams_for_chapter(chapter_id: int, limit: int = 20):
    """
    Получает топ биграмм для всего раздела
    Группировка по биграмме: суммирование частот
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    b.bigram,
                    b.word1,
                    b.word2,
                    b.frequency,
                    b.contexts,
                    d.id as doc_id,
                    d.title
                FROM new_bigrams b
                INNER JOIN documents d ON b.id_documents = d.id
                WHERE d.chapter_id = %s
                ORDER BY b.frequency DESC
            """, (chapter_id,))
            all_bigrams = cur.fetchall()

        if not all_bigrams:
            return []

        # Агрегируем биграммы: суммируем частоты
        aggregated = defaultdict(lambda: {
            'word1': '',
            'word2': '',
            'total_freq': 0,
            'contexts': [],
            'documents': [],
            'doc_count': 0
        })

        for bigram, w1, w2, freq, contexts, doc_id, title in all_bigrams:
            if bigram not in aggregated:
                aggregated[bigram]['word1'] = w1
                aggregated[bigram]['word2'] = w2

            aggregated[bigram]['total_freq'] += freq

            # Добавляем контексты (до 5 уникальных)
            if contexts:
                for ctx in contexts.split('||'):
                    if ctx and ctx not in aggregated[bigram]['contexts']:
                        aggregated[bigram]['contexts'].append(ctx)
                        if len(aggregated[bigram]['contexts']) >= 5:
                            break

            # Запоминаем документы (до 5)
            doc_ref = f"ID:{doc_id}"
            if doc_ref not in aggregated[bigram]['documents']:
                aggregated[bigram]['documents'].append(doc_ref)
                aggregated[bigram]['doc_count'] += 1

        # Преобразуем в список и сортируем по суммарной частоте
        result = []
        for bigram, data in aggregated.items():
            result.append({
                'bigram': bigram,
                'word1': data['word1'],
                'word2': data['word2'],
                'total_frequency': data['total_freq'],
                'doc_count': data['doc_count'],
                'contexts': data['contexts'],
                'documents': data['documents']
            })

        result.sort(key=lambda x: x['total_frequency'], reverse=True)
        return result[:limit]

    finally:
        conn.close()


def display_bigrams_document(bigrams, doc_info):
    """Выводит биграммы для одного документа (БЕЗ ограничений)"""
    if not bigrams:
        print("\n❌ Для этого документа биграммы не найдены")
        print("   Возможно, документ не был обработан или текст слишком короткий")
        return

    print(f"\n{'=' * 80}")
    print(f"📄 ИНФОРМАЦИЯ О ДОКУМЕНТЕ")
    print(f"{'=' * 80}")
    print(f"   ID: {doc_info[0]}")
    print(f"   Название: {doc_info[1][:150] if doc_info[1] else 'Без названия'}")
    print(f"   Тип: {doc_info[2] if doc_info[2] else 'Не указан'}")
    print(f"   Раздел: {doc_info[3] if doc_info[3] else 'Не указан'}")

    print(f"\n{'=' * 80}")
    print(f"📊 ВСЕ БИГРАММЫ ПО ЧАСТОТЕ (всего: {len(bigrams)})")
    print(f"{'=' * 80}")

    for i, (bigram, w1, w2, freq, contexts) in enumerate(bigrams, 1):
        print(f"\n{i:2d}. Биграмма: \"{bigram}\"")
        print(f"    Слова: {w1} + {w2}")
        print(f"    Частота: {freq} раз(а)")

        if contexts:
            context_list = [ctx.strip() for ctx in contexts.split('||') if ctx.strip()]
            print(f"    Количество контекстов: {len(context_list)}")
            print(f"    ВСЕ КОНТЕКСТЫ:")
            for j, ctx in enumerate(context_list, 1):
                ctx_clean = re.sub(r'\s+', ' ', ctx).strip()
                highlighted = ctx_clean.replace(bigram, f"***{bigram}***")
                print(f"      {j:2d}. ...{highlighted}...")

            if len(context_list) == freq:
                print(f"    ✅ Количество контекстов ({len(context_list)}) совпадает с частотой ({freq})")
            else:
                print(f"    ⚠️ Количество контекстов ({len(context_list)}) не совпадает с частотой ({freq})")
        else:
            print("    ❌ Контексты не найдены")

        if i < len(bigrams):
            print(f"    {'─' * 70}")

    # Статистика
    print(f"\n{'=' * 80}")
    print(f"📈 СТАТИСТИКА ПО ДОКУМЕНТУ")
    print(f"{'=' * 80}")
    print(f"   Всего биграмм: {len(bigrams)}")

    if bigrams:
        best = bigrams[0]
        print(f"   Самая частотная биграмма: '{best[0]}' ({best[3]} раз)")

        # Считаем общее количество контекстов
        total_contexts = 0
        for b in bigrams:
            if b[4]:
                contexts_count = len([ctx for ctx in b[4].split('||') if ctx.strip()])
                total_contexts += contexts_count
        print(f"   Всего контекстов по всем биграммам: {total_contexts}")


def display_bigrams_chapter(bigrams, chapter_info):
    """Выводит биграммы для раздела (топ-20 с группировкой)"""
    if not bigrams:
        print("\n❌ Для этого раздела биграммы не найдены")
        return

    print(f"\n{'=' * 80}")
    print(f"📚 ИНФОРМАЦИЯ О РАЗДЕЛЕ")
    print(f"{'=' * 80}")
    print(f"   ID раздела: {chapter_info[0]}")
    print(f"   Название: {chapter_info[1] if chapter_info[1] else 'Без названия'}")

    print(f"\n{'=' * 80}")
    print(f"📊 ТОП-{len(bigrams)} БИГРАММ ПО РАЗДЕЛУ (суммарная частота)")
    print(f"{'=' * 80}")

    for i, item in enumerate(bigrams, 1):
        print(f"\n{i:2d}. Биграмма: \"{item['bigram']}\"")
        print(f"    Слова: {item['word1']} + {item['word2']}")
        print(f"    Суммарная частота по разделу: {item['total_frequency']} раз(а)")
        print(f"    Встречается в {item['doc_count']} документах")

        if item['contexts']:
            print(f"    Контексты (первые 5):")
            for j, ctx in enumerate(item['contexts'][:5], 1):
                ctx_clean = re.sub(r'\s+', ' ', ctx).strip()
                highlighted = ctx_clean.replace(item['bigram'], f"***{item['bigram']}***")
                print(f"      {j}. ...{highlighted[:120]}...")
            if len(item['contexts']) > 5:
                print(f"      ... и еще {len(item['contexts']) - 5} контекстов")
        else:
            print("    ❌ Контексты не найдены")

        if item['documents']:
            print(f"    Документы: {', '.join(item['documents'][:5])}")
            if len(item['documents']) > 5:
                print(f"      ... и еще {len(item['documents']) - 5} документов")

        if i < len(bigrams):
            print(f"    {'─' * 70}")


def show_documents_list():
    """Показывает список всех документов с биграммами"""
    documents = get_all_documents()

    if not documents:
        print("\n❌ Нет документов с биграммами")
        print("   Сначала запустите скрипт build_bigrams.py")
        return None

    print(f"\n{'=' * 80}")
    print("📚 СПИСОК ДОКУМЕНТОВ С БИГРАММАМИ")
    print(f"{'=' * 80}")
    print(f"\n{'ID':<6} {'Раздел':<8} {'Тип':<15} {'Название'}")
    print(f"{'─' * 80}")

    for doc_id, title, doc_type, chapter_id in documents:
        title_short = title[:55] if title else "Без названия"
        doc_type_short = doc_type[:15] if doc_type else "Не указан"
        chapter_short = str(chapter_id) if chapter_id else "-"
        print(f"{doc_id:<6} {chapter_short:<8} {doc_type_short:<15} {title_short}")

    print(f"\n📊 Всего документов с биграммами: {len(documents)}")
    return documents


def show_chapters_list():
    """Показывает список всех разделов"""
    chapters = get_chapters()

    if not chapters:
        print("\n❌ Нет доступных разделов")
        return None

    print(f"\n{'=' * 80}")
    print("📚 СПИСОК РАЗДЕЛОВ")
    print(f"{'=' * 80}")
    print(f"\n{'ID':<6} {'Название раздела'}")
    print(f"{'─' * 80}")

    for ch_id, ch_name in chapters:
        print(f"{ch_id:<6} {ch_name[:70] if ch_name else 'Без названия'}")

    print(f"\n📊 Всего разделов: {len(chapters)}")
    return chapters


def interactive_search():
    """Интерактивный режим поиска биграмм"""
    print("\n" + "=" * 80)
    print("🔍 ПОИСК БИГРАММ ПО ЧАСТОТЕ")
    print("=" * 80)

    print("\nВыберите режим поиска:")
    print("  1. Поиск в конкретном документе (все биграммы)")
    print("  2. Поиск по разделу (топ-20 с группировкой)")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        # Поиск по документу
        documents = show_documents_list()
        if not documents:
            return

        # Выбор документа
        while True:
            try:
                doc_input = input("\n👉 Введите ID документа (или 'q' для выхода): ").strip()

                if doc_input.lower() == 'q':
                    print("\n👋 Выход")
                    return

                doc_id = int(doc_input)

                doc_exists = any(doc[0] == doc_id for doc in documents)
                if doc_exists:
                    break
                else:
                    print(f"❌ Документ с ID {doc_id} не найден в списке")

            except ValueError:
                print("❌ Пожалуйста, введите корректный числовой ID")
            except KeyboardInterrupt:
                print("\n👋 Отмена")
                return

        # Получаем информацию о документе
        doc_info = get_document_info(doc_id)
        if not doc_info:
            print(f"❌ Документ с ID {doc_id} не найден")
            return

        # Получаем биграммы
        print(f"\n🔄 Поиск биграмм для документа ID: {doc_id}...")
        bigrams = get_bigrams_for_document(doc_id)

        # Выводим результаты
        display_bigrams_document(bigrams, doc_info)

    elif choice == '2':
        # Поиск по разделу
        chapters = show_chapters_list()
        if not chapters:
            return

        # Выбор раздела
        while True:
            try:
                chapter_input = input("\n👉 Введите ID раздела (или 'q' для выхода): ").strip()

                if chapter_input.lower() == 'q':
                    print("\n👋 Выход")
                    return

                chapter_id = int(chapter_input)

                chapter_exists = any(ch[0] == chapter_id for ch in chapters)
                if chapter_exists:
                    break
                else:
                    print(f"❌ Раздел с ID {chapter_id} не найден в списке")

            except ValueError:
                print("❌ Пожалуйста, введите корректный числовой ID")
            except KeyboardInterrupt:
                print("\n👋 Отмена")
                return

        # Получаем информацию о разделе
        chapter_info = next((ch for ch in chapters if ch[0] == chapter_id), None)
        if not chapter_info:
            print(f"❌ Раздел с ID {chapter_id} не найден")
            return

        # Получаем биграммы по разделу
        print(f"\n🔄 Поиск биграмм для раздела ID: {chapter_id}...")
        bigrams = get_bigrams_for_chapter(chapter_id, limit=20)

        # Выводим результаты
        display_bigrams_chapter(bigrams, chapter_info)

    else:
        print("❌ Неверный выбор!")


def main():
    """Главная функция"""
    print("🔍 СИСТЕМА ПОИСКА БИГРАММ ПО ЧАСТОТЕ")
    print("=" * 80)

    while True:
        print("\n📋 МЕНЮ:")
        print("  1. Поиск биграмм")
        print("  2. Показать список документов с биграммами")
        print("  3. Показать список разделов")
        print("  4. Выход")

        choice = input("\n👉 Ваш выбор (1-4): ").strip()

        if choice == '1':
            interactive_search()
        elif choice == '2':
            show_documents_list()
        elif choice == '3':
            show_chapters_list()
        elif choice == '4':
            print("\n👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор!")


if __name__ == "__main__":
    main()