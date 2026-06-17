import psycopg2
import re

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
    """Получает список всех документов с коллокациями"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT d.id, d.title, d.type
                FROM documents d
                INNER JOIN collocations c ON d.id = c.id_documents
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
                SELECT id, title, type 
                FROM documents 
                WHERE id = %s
            """, (doc_id,))
            return cur.fetchone()
    finally:
        conn.close()


def get_collocations_for_document(doc_id: int, limit: int = 10):
    """
    Получает топ-N коллокаций для конкретного документа
    Сортировка по Likelihood Score (от большего к меньшему)
    """
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    collocation, 
                    word1, 
                    word2, 
                    frequency, 
                    likelihood_score, 
                    contexts
                FROM collocations
                WHERE id_documents = %s
                ORDER BY likelihood_score DESC
                LIMIT %s
            """, (doc_id, limit))
            return cur.fetchall()
    finally:
        conn.close()


def display_collocations(collocations, doc_info):
    """Красиво выводит коллокации для одного документа со ВСЕМИ контекстами"""
    if not collocations:
        print("\n❌ Для этого документа коллокации не найдены")
        print("   Возможно, документ не был обработан или текст слишком короткий")
        return

    print(f"\n{'=' * 80}")
    print(f"📄 ИНФОРМАЦИЯ О ДОКУМЕНТЕ")
    print(f"{'=' * 80}")
    print(f"   ID: {doc_info[0]}")
    print(f"   Название: {doc_info[1][:150] if doc_info[1] else 'Без названия'}")
    print(f"   Тип: {doc_info[2] if doc_info[2] else 'Не указан'}")

    print(f"\n{'=' * 80}")
    print(f"📊 ТОП-{len(collocations)} КОЛЛОКАЦИЙ ПО LIKELIHOOD RATIO")
    print(f"{'=' * 80}")

    for i, (colloc, w1, w2, freq, score, contexts) in enumerate(collocations, 1):
        print(f"\n{i:2d}. Коллокация: \"{colloc}\"")
        print(f"    Слова: {w1} + {w2}")
        print(f"    Частота: {freq} раз(а)")
        print(f"    Likelihood Ratio: {score:.4f}")

        if contexts:
            # Разбиваем строку контекстов по разделителю '||'
            context_list = contexts.split('||')
            # Убираем пустые строки
            context_list = [ctx.strip() for ctx in context_list if ctx.strip()]

            print(f"    Количество контекстов: {len(context_list)}")
            print(f"    ВСЕ КОНТЕКСТЫ:")

            # Выводим ВСЕ контексты (без ограничения)
            for j, ctx in enumerate(context_list, 1):
                # Очищаем от лишних пробелов
                ctx_clean = re.sub(r'\s+', ' ', ctx).strip()
                # Подсвечиваем коллокацию
                highlighted = ctx_clean.replace(colloc, f"***{colloc}***")
                print(f"      {j:2d}. ...{highlighted}...")

        else:
            print("    ❌ Контексты не найдены")

        # Разделитель между коллокациями
        if i < len(collocations):
            print(f"    {'─' * 70}")

    # Статистика по документу
    print(f"\n{'=' * 80}")
    print(f"📈 СТАТИСТИКА ПО ДОКУМЕНТУ")
    print(f"{'=' * 80}")
    print(f"   Всего коллокаций в топе: {len(collocations)}")

    if collocations:
        best = collocations[0]
        print(f"   Лучшая коллокация: '{best[0]}'")
        print(f"   Максимальный Likelihood Ratio: {best[4]:.4f}")

        # Считаем средний Likelihood
        avg_score = sum(c[4] for c in collocations) / len(collocations)
        print(f"   Средний Likelihood Ratio: {avg_score:.4f}")

        # Считаем общее количество контекстов
        total_contexts = 0
        for c in collocations:
            if c[5]:
                contexts_count = len([ctx for ctx in c[5].split('||') if ctx.strip()])
                total_contexts += contexts_count
        print(f"   Всего контекстов по всем коллокациям: {total_contexts}")


def show_documents_list():
    """Показывает список всех документов с коллокациями"""
    documents = get_all_documents()

    if not documents:
        print("\n❌ Нет документов с коллокациями")
        print("   Сначала запустите скрипт build_collocations.py")
        return None

    print(f"\n{'=' * 80}")
    print("📚 СПИСОК ДОКУМЕНТОВ С КОЛЛОКАЦИЯМИ")
    print(f"{'=' * 80}")
    print(f"\n{'ID':<6} {'Тип':<15} {'Название'}")
    print(f"{'─' * 80}")

    for doc_id, title, doc_type in documents:
        title_short = title[:60] if title else "Без названия"
        doc_type_short = doc_type[:15] if doc_type else "Не указан"
        print(f"{doc_id:<6} {doc_type_short:<15} {title_short}")

    print(f"\n📊 Всего документов с коллокациями: {len(documents)}")
    return documents


def interactive_search():
    """Интерактивный режим поиска коллокаций в документе"""
    print("\n" + "=" * 80)
    print("🔍 ПОИСК КОЛЛОКАЦИЙ В ДОКУМЕНТЕ (LIKELIHOOD RATIO)")
    print("=" * 80)

    # Показываем список документов
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

            # Проверяем, существует ли документ
            doc_exists = any(doc[0] == doc_id for doc in documents)
            if doc_exists:
                break
            else:
                print(f"❌ Документ с ID {doc_id} не найден в списке")
                print("   Пожалуйста, выберите ID из списка выше")

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

    # Выбор количества коллокаций
    while True:
        try:
            limit_input = input("\n👉 Введите количество коллокаций для вывода (по умолчанию 10): ").strip()

            if not limit_input:
                limit = 10
                break

            limit = int(limit_input)
            if 1 <= limit <= 50:
                break
            else:
                print("❌ Пожалуйста, введите число от 1 до 50")

        except ValueError:
            print("❌ Пожалуйста, введите корректное число")
        except KeyboardInterrupt:
            print("\n👋 Отмена")
            return

    # Получаем коллокации
    print(f"\n🔄 Поиск коллокаций для документа ID: {doc_id}...")
    collocations = get_collocations_for_document(doc_id, limit=limit)

    # Выводим результаты
    display_collocations(collocations, doc_info)


def main():
    """Главная функция"""
    print("🔍 СИСТЕМА ПОИСКА КОЛЛОКАЦИЙ В ДОКУМЕНТЕ")
    print("=" * 80)

    while True:
        print("\n📋 МЕНЮ:")
        print("  1. Поиск коллокаций в документе")
        print("  2. Показать список документов с коллокациями")
        print("  3. Выход")

        choice = input("\n👉 Ваш выбор (1-3): ").strip()

        if choice == '1':
            interactive_search()
        elif choice == '2':
            show_documents_list()
        elif choice == '3':
            print("\n👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор! Пожалуйста, выберите 1, 2 или 3")


if __name__ == "__main__":
    main()