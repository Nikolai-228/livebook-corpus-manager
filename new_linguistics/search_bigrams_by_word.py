import psycopg2
import re
from pymorphy3 import MorphAnalyzer

DB_CONFIG = {
    'host': 'livebook-team.duckdns.org',
    'port': 5432,
    'user': 'team_user',
    'password': 'book_live',
    'database': 'livebook_corpus'
}


def connect_db():
    return psycopg2.connect(**DB_CONFIG)


def search_bigrams_by_word(search_word: str, doc_id: int = None, chapter_id: int = None):
    """
    Поиск биграмм по слову
    - doc_id: если указан, поиск только в этом документе
    - chapter_id: если указан, поиск по всем документам раздела
    """
    morph = MorphAnalyzer()

    # Лемматизируем слово
    try:
        search_lemma = morph.parse(search_word.lower())[0].normal_form
    except:
        search_lemma = search_word.lower()

    print(f"\n🔍 Поиск биграмм со словом: '{search_word}' (лемма: '{search_lemma}')")

    conn = connect_db()
    try:
        with conn.cursor() as cur:
            # Базовый запрос
            query = """
                SELECT 
                    b.id_documents,
                    d.title,
                    b.bigram,
                    b.word1,
                    b.word2,
                    b.frequency,
                    b.contexts
                FROM new_bigrams b
                INNER JOIN documents d ON b.id_documents = d.id
                WHERE (b.word1 = %s OR b.word2 = %s)
            """
            params = [search_lemma, search_lemma]

            # Добавляем фильтры
            if doc_id:
                query += " AND b.id_documents = %s"
                params.append(doc_id)
            elif chapter_id:
                query += " AND d.chapter_id = %s"
                params.append(chapter_id)

            query += " ORDER BY b.frequency DESC"

            cur.execute(query, params)
            results = cur.fetchall()

        if not results:
            print("❌ Биграммы не найдены")
            return

        print(f"\n✅ Найдено: {len(results)} биграмм\n")
        print("=" * 80)

        for i, (doc_id, title, bigram, w1, w2, freq, contexts) in enumerate(results, 1):
            print(f"\n{i:2d}. \"{bigram}\"  (частота: {freq})")
            print(f"    Документ: {title[:80]}")

            if contexts:
                ctx_list = [c.strip() for c in contexts.split('||') if c.strip()]
                print(f"    Контексты ({len(ctx_list)}):")
                for ctx in ctx_list:
                    ctx_clean = re.sub(r'\s+', ' ', ctx).strip()
                    highlighted = ctx_clean.replace(bigram, f"***{bigram}***")
                    print(f"      ...{highlighted}...")
            print("    " + "-" * 70)

        print(f"\n{'=' * 80}")
        print(f"📊 Всего биграмм: {len(results)}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()


def get_documents_list():
    """Показывает список документов"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT d.id, d.title, d.type
                FROM documents d
                INNER JOIN new_bigrams b ON d.id = b.id_documents
                ORDER BY d.id
            """)
            docs = cur.fetchall()

        if not docs:
            print("\n❌ Нет документов с биграммами")
            return None

        print("\n📚 ДОКУМЕНТЫ С БИГРАММАМИ:")
        print("─" * 70)
        for doc_id, title, doc_type in docs:
            print(f"  ID: {doc_id}  |  {title[:60]}")
        return docs
    finally:
        conn.close()


def get_chapters_list():
    """Показывает список разделов"""
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM chapters ORDER BY id")
            chapters = cur.fetchall()

        if not chapters:
            print("\n❌ Нет разделов")
            return None

        print("\n📚 РАЗДЕЛЫ:")
        print("─" * 70)
        for ch_id, ch_name in chapters:
            print(f"  ID: {ch_id}  |  {ch_name[:60]}")
        return chapters
    finally:
        conn.close()


def interactive():
    print("=" * 70)
    print("🔍 ПОИСК БИГРАММ ПО СЛОВУ")
    print("=" * 70)

    while True:
        print("\n📋 МЕНЮ:")
        print("  1. Поиск в документе")
        print("  2. Поиск в разделе")
        print("  3. Выход")

        choice = input("\n👉 Выбор: ").strip()

        if choice == '1':
            docs = get_documents_list()
            if not docs:
                continue

            try:
                doc_id = int(input("\n👉 ID документа: ").strip())
                if not any(d[0] == doc_id for d in docs):
                    print("❌ Документ не найден")
                    continue
            except:
                print("❌ Введите число")
                continue

            word = input("👉 Слово для поиска: ").strip()
            if not word:
                print("❌ Введите слово")
                continue

            search_bigrams_by_word(word, doc_id=doc_id)

        elif choice == '2':
            chapters = get_chapters_list()
            if not chapters:
                continue

            try:
                ch_id = int(input("\n👉 ID раздела: ").strip())
                if not any(c[0] == ch_id for c in chapters):
                    print("❌ Раздел не найден")
                    continue
            except:
                print("❌ Введите число")
                continue

            word = input("👉 Слово для поиска: ").strip()
            if not word:
                print("❌ Введите слово")
                continue

            search_bigrams_by_word(word, chapter_id=ch_id)

        elif choice == '3':
            print("\n👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор")


if __name__ == "__main__":
    interactive()