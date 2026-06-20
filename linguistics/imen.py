import psycopg2
import re
from collections import defaultdict, Counter
import json
# Подключение к БД
from db_connection import connect_db, DB_CONFIG

def get_all_documents():
    """Получает все документы с оригинальным текстом"""
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

def get_document_info(doc_id: int):
    """Получает информацию о документе (название, тип, содержание)"""
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
        print(f"Ошибка при получении информации о документе: {e}")
        return None
    finally:
        conn.close()

class RussianNER:
    """Класс для извлечения именованных сущностей из русских текстов"""
    def __init__(self):
        # Стоп-слова для фильтрации
        self.stop_words = {
            'этот', 'это', 'эти', 'этой', 'этого', 'этом', 'этому', 'этим', 'этими',
            'весь', 'вся', 'все', 'всех', 'всем', 'всеми', 'всё',
            'сам', 'сама', 'само', 'сами', 'самого', 'самой', 'самих',
            'тот', 'та', 'то', 'те', 'того', 'той', 'тех', 'тем', 'теми',
            'наш', 'наша', 'наше', 'наши', 'нашего', 'нашей', 'наших', 'нашим', 'нашими',
            'ваш', 'ваша', 'ваше', 'ваши', 'вашего', 'вашей', 'ваших', 'вашим', 'вашими',
            'свой', 'своя', 'свое', 'свои', 'своего', 'своей', 'своих', 'своим', 'своими',
            'который', 'которая', 'которое', 'которые', 'которого', 'которой', 'которых',
            'один', 'одна', 'одно', 'одни', 'одного', 'одной', 'одних',
            'также', 'где', 'когда', 'тогда', 'затем', 'потом', 'теперь',
            'уже', 'еще', 'ещё', 'вот', 'лишь', 'только', 'почти',
            'как', 'так', 'что', 'чтобы', 'будто', 'словно',
            'без', 'для', 'до', 'за', 'из', 'к', 'на', 'над', 'о', 'об', 'от', 'по',
            'под', 'при', 'про', 'с', 'со', 'у', 'через', 'в', 'на', 'с', 'по', 'к', 'у', 'от', 'из',
            'года', 'год', 'лет', 'месяц', 'день', 'ночь', 'утро', 'вечер'
        }
        # Список слов-маркеров для имен
        self.person_markers = {
            'профессор', 'доцент', 'преподаватель', 'ректор', 'декан', 'заведующий',
            'директор', 'президент', 'министр', 'депутат', 'губернатор', 'мэр',
            'глава', 'ученый', 'академик', 'писатель', 'поэт', 'художник',
            'композитор', 'архитектор', 'инженер', 'доктор', 'руководитель',
            'председатель', 'начальник', 'генеральный', 'главный', 'генерал',
            'полковник', 'майор', 'капитан', 'сержант', 'солдат', 'офицер',
            'студент', 'аспирант', 'выпускник', 'преподаватель'
        }
        # Слова-маркеры для организаций
        self.org_markers = {
            'институт', 'университет', 'академия', 'школа', 'колледж',
            'компания', 'завод', 'фабрика', 'корпорация', 'холдинг',
            'министерство', 'департамент', 'управление', 'центр',
            'лаборатория', 'банк', 'фонд', 'агентство', 'ассоциация',
            'союз', 'федерация', 'объединение', 'библиотека', 'музей',
            'театр', 'студия', 'редакция', 'фирма', 'предприятие',
            'организация', 'учреждение', 'НИИ', 'КБ', 'ООО', 'ЗАО', 'ОАО', 'ПАО'
        }

    def extract_persons(self, text: str) -> list:
        """Извлечение имен людей из текста"""
        persons = set()

        # Паттерн 1: Имя + Фамилия (с возможным отчеством)
        # Ищем слова с заглавной буквы, идущие подряд
        pattern1 = r'\b([А-Я][а-я]{2,}(?:\s+[А-Я][а-я]{2,}){1,2})\b'
        matches = re.findall(pattern1, text)

        for match in matches:
            # Проверяем, что это не организация и не стоп-слово
            words = match.split()
            if len(words) >= 2 and len(words) <= 3:
                # Проверяем, что все слова начинаются с заглавной
                if all(w[0].isupper() and w[0] != 'И' for w in words):
                    # Проверяем, что это не организация
                    is_org = False
                    for marker in self.org_markers:
                        if marker in match.lower():
                            is_org = True
                            break
                    if not is_org:
                        persons.add(match)

        # Паттерн 2: Инициалы + Фамилия (И.И. Иванов)
        pattern2 = r'\b([А-Я]\.\s*[А-Я]\.\s*[А-Я][а-я]{2,})\b'
        matches = re.findall(pattern2, text)
        for match in matches:
            persons.add(match)

        # Паттерн 3: Фамилия + Инициалы (Иванов И.И.)
        pattern3 = r'\b([А-Я][а-я]{2,}\s+[А-Я]\.\s*[А-Я]\.)\b'
        matches = re.findall(pattern3, text)
        for match in matches:
            persons.add(match)

        # Паттерн 4: Слово-маркер + Имя Фамилия
        for marker in self.person_markers:
            pattern4 = rf'\b{marker}\s+([А-Я][а-я]{{2,}}(?:\s+[А-Я][а-я]{{2,}}){{1,2}})\b'
            matches = re.findall(pattern4, text, re.IGNORECASE)
            for match in matches:
                if len(match.split()) >= 2:
                    persons.add(match)

        # Паттерн 5: Имя Фамилия после слов "товарищ", "гражданин" и т.д.
        pattern5 = r'\b(?:товарищ|гражданин|господин)\s+([А-Я][а-я]{2,}\s+[А-Я][а-я]{2,})\b'
        matches = re.findall(pattern5, text, re.IGNORECASE)
        for match in matches:
            persons.add(match)

        # Фильтруем слишком короткие или подозрительные имена
        filtered_persons = set()
        for person in persons:
            words = person.split()
            # Проверяем длину слов
            if all(2 <= len(w) <= 20 for w in words):
                # Проверяем, что это не название организации
                is_org = False
                for marker in self.org_markers:
                    if marker in person.lower():
                        is_org = True
                        break
                if not is_org:
                    filtered_persons.add(person)

        return list(filtered_persons)

    def extract_organizations(self, text: str) -> list:
        """Извлечение названий организаций"""
        organizations = set()

        # Паттерн 1: Название с маркером организации
        for marker in self.org_markers:
            # Ищем маркер + название (с заглавной буквы)
            pattern1 = rf'\b{marker}\s+([А-Я][а-яА-Я\-]+(?:\s+[А-Я][а-яА-Я\-]+)*)\b'
            matches = re.findall(pattern1, text, re.IGNORECASE)
            for match in matches:
                if len(match) > 2:
                    full_name = f"{marker} {match}"
                    organizations.add(full_name)

            # Ищем название + маркер
            pattern2 = rf'\b([А-Я][а-яА-Я\-]+(?:\s+[А-Я][а-яА-Я\-]+)*)\s+{marker}\b'
            matches = re.findall(pattern2, text, re.IGNORECASE)
            for match in matches:
                if len(match) > 2:
                    full_name = f"{match} {marker}"
                    organizations.add(full_name)

        # Паттерн 2: Аббревиатуры
        pattern3 = r'\b([А-Я]{2,}(?:\s*[А-Я]{2,})*)\b'
        matches = re.findall(pattern3, text)
        for match in matches:
            if len(match) >= 2 and match not in self.stop_words:
                organizations.add(match)

        # Паттерн 3: Названия в кавычках
        pattern4 = r'["«]([А-Я][а-яА-Я\-]+(?:\s+[А-Я][а-яА-Я\-]+)*)["»]'
        matches = re.findall(pattern4, text)
        for match in matches:
            if len(match) > 2:
                # Проверяем, что это не имя человека
                is_person = False
                words = match.split()
                if len(words) >= 2 and all(w[0].isupper() for w in words):
                    # Проверяем по маркерам
                    for marker in self.person_markers:
                        if marker in match.lower():
                            is_person = True
                            break
                if not is_person:
                    organizations.add(match)

        return list(organizations)

    def extract_locations(self, text: str) -> list:
        """Извлечение географических названий"""
        locations = set()

        # Паттерн 1: С маркером места
        location_markers = {
            'город', 'поселок', 'деревня', 'село', 'район', 'край',
            'область', 'республика', 'улица', 'проспект', 'площадь',
            'бульвар', 'переулок', 'река', 'озеро', 'море', 'гора',
            'страна', 'столица', 'регион', 'территория'
        }

        for marker in location_markers:
            pattern = rf'\b{marker}\s+([А-Я][а-яА-Я\-]+(?:\s+[А-Я][а-яА-Я\-]+)*)\b'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) > 2:
                    locations.add(f"{marker} {match}")

        # Паттерн 2: Сокращения (г., ул., пр.)
        pattern2 = r'\b(?:г\.|ул\.|пр\.)\s+([А-Я][а-яА-Я\-]+(?:\s+[А-Я][а-яА-Я\-]+)*)\b'
        matches = re.findall(pattern2, text)
        for match in matches:
            if len(match) > 2:
                locations.add(match)

        return list(locations)

    def extract_dates(self, text: str) -> list:
        """Извлечение дат"""
        dates = set()

        patterns = [
            r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)(?:\s+\d{4})?',
            r'\d{2}\.\d{2}\.\d{4}',
            r'\d{4}[\-]\d{2}[\-]\d{2}',
            r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)',
            r'\d{4}\s+год(?:а)?',
            r'(?:в|с|до|после|начиная\s+с)\s+\d{4}\s+год(?:а)?',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                dates.add(match.strip())

        return list(dates)

    def extract_money(self, text: str) -> list:
        """Извлечение денег"""
        money = set()

        patterns = [
            r'\d+[\.,]?\d*\s*(?:рубль|руб|рублей|рубля|₽|RUB)',
            r'\d+[\.,]?\d*\s*(?:доллар|долларов|доллара|\$|USD)',
            r'\d+[\.,]?\d*\s*(?:евро|€|EUR)',
            r'\d+\s+тысяч(?:а|и)?\s+(?:рубль|руб|доллар|евро)',
            r'\d+\s+миллион(?:а|ов)?\s+(?:рубль|руб|доллар|евро)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                money.add(match.strip())

        return list(money)

    def extract_percents(self, text: str) -> list:
        """Извлечение процентов"""
        percents = set()

        patterns = [
            r'\d+[\.,]?\d*\s*%',
            r'\d+[\.,]?\d*\s*(?:процент|процента|процентов)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                percents.add(match.strip())

        return list(percents)

    def extract_all(self, text: str) -> dict:
        """Извлечение всех типов сущностей"""
        if not text:
            return {}

        entities = {
            'PERSON': self.extract_persons(text),
            'ORGANIZATION': self.extract_organizations(text),
            'LOCATION': self.extract_locations(text),
            'DATE': self.extract_dates(text),
            'MONEY': self.extract_money(text),
            'PERCENT': self.extract_percents(text)
        }

        # Удаляем пустые списки
        return {k: v for k, v in entities.items() if v}


def find_entity_contexts(text: str, entity: str, context_size: int = 70) -> list:
    """Находит все контексты для сущности в тексте"""
    contexts = []
    text_lower = text.lower()
    entity_lower = entity.lower()
    pos = 0

    while True:
        found = text_lower.find(entity_lower, pos)
        if found == -1:
            break
        start = max(0, found - context_size)
        end = min(len(text), found + len(entity) + context_size)
        context = text[start:end].replace('\n', ' ')
        contexts.append(context)
        pos = found + 1

    return contexts


def extract_entities_from_document(doc_id: int, top_n: int = 20):
    """Извлекает именованные сущности из документа"""
    print(f"\n{'=' * 70}")
    print(f"🔍 ИЗВЛЕЧЕНИЕ ИМЕНОВАННЫХ СУЩНОСТЕЙ")
    print(f"{'=' * 70}")
    print(f"📄 ДОКУМЕНТ ID: {doc_id}")
    print(f"{'=' * 70}")

    doc_info = get_document_info(doc_id)
    if not doc_info:
        print("❌ Документ не найден")
        return

    if not doc_info['content']:
        print("❌ Документ пуст")
        return

    print(f"\n📄 Информация о документе:")
    print(f"   ID: {doc_id}")
    print(f"   Название: {doc_info['title'][:150] if doc_info['title'] else 'Без названия'}")
    print(f"   Тип файла: {doc_info['type'] if doc_info['type'] else 'Не указан'}")
    print(f"   Размер текста: {len(doc_info['content'])} символов")

    print(f"\n🔄 Извлечение сущностей...")

    ner = RussianNER()
    entities = ner.extract_all(doc_info['content'])

    if not entities:
        print("\n❌ Сущности не найдены")
        return

    print(f"\n📊 НАЙДЕННЫЕ СУЩНОСТИ:")
    print(f"{'─' * 70}")

    entity_types = {
        'PERSON': '👤 Люди',
        'ORGANIZATION': '🏢 Организации',
        'LOCATION': '📍 Места',
        'DATE': '📅 Даты',
        'MONEY': '💰 Деньги',
        'PERCENT': '📊 Проценты'
    }

    total_entities = 0

    for entity_type, entity_list in entities.items():
        if entity_list:
            type_name = entity_types.get(entity_type, entity_type)
            print(f"\n📌 {type_name}:")
            print(f"   Найдено: {len(entity_list)}")

            entity_freq = {}
            for entity in entity_list:
                contexts = find_entity_contexts(doc_info['content'], entity)
                entity_freq[entity] = len(contexts)

            sorted_entities = sorted(entity_freq.items(), key=lambda x: x[1], reverse=True)

            for i, (entity, freq) in enumerate(sorted_entities[:top_n], 1):
                contexts = find_entity_contexts(doc_info['content'], entity)

                print(f"\n   {i:2d}. \"{entity}\"")
                print(f"       Частота: {freq} раз(а)")

                if contexts:
                    print(f"       Контексты:")
                    for j, ctx in enumerate(contexts[:2], 1):
                        ctx_clean = re.sub(r'\s+', ' ', ctx)
                        highlighted = ctx_clean.replace(
                            entity,
                            f"***{entity}***"
                        )
                        print(f"         {j}. ...{highlighted[:150]}...")
                    if len(contexts) > 2:
                        print(f"         ... и еще {len(contexts) - 2} контекстов")

            total_entities += len(entity_list)

    print(f"\n📈 СТАТИСТИКА ПО ДОКУМЕНТУ:")
    print(f"   Всего типов сущностей: {len([e for e in entities if entities[e]])}")
    print(f"   Всего сущностей: {total_entities}")

    return entities


def extract_entities_all_documents(top_n_per_doc: int = 20, top_n_total: int = 30):
    """Извлекает сущности из всех документов и показывает статистику"""
    print(f"\n{'=' * 70}")
    print(f"🔍 СТАТИСТИКА ИМЕНОВАННЫХ СУЩНОСТЕЙ ПО ВСЕМ ДОКУМЕНТАМ")
    print(f"{'=' * 70}")

    documents = get_all_documents()
    if not documents:
        print("❌ Нет документов")
        return

    all_entities = defaultdict(list)
    ner = RussianNER()

    print(f"\n📊 ОБРАБОТКА ДОКУМЕНТОВ:")
    print(f"{'─' * 70}")

    for doc_id, title, doc_type, content in documents:
        if not content:
            continue

        print(f"\n📄 Обработка: {title[:50] if title else 'Без названия'} (ID: {doc_id})")

        entities = ner.extract_all(content)

        if entities:
            for entity_type, entity_list in entities.items():
                all_entities[entity_type].extend(entity_list)
            print(f"   ✅ Найдено сущностей: {sum(len(e) for e in entities.values())}")
        else:
            print(f"   ⚠️ Сущности не найдены")

    if not all_entities:
        print("\n❌ Сущности не найдены ни в одном документе")
        return

    print(f"\n{'=' * 70}")
    print(f"📊 ОБЩАЯ СТАТИСТИКА ПО ВСЕМ ДОКУМЕНТАМ:")
    print(f"{'=' * 70}")

    entity_types = {
        'PERSON': '👤 Люди',
        'ORGANIZATION': '🏢 Организации',
        'LOCATION': '📍 Места',
        'DATE': '📅 Даты',
        'MONEY': '💰 Деньги',
        'PERCENT': '📊 Проценты'
    }

    for entity_type, entity_list in all_entities.items():
        if entity_list:
            counter = Counter(entity_list)
            type_name = entity_types.get(entity_type, entity_type)

            print(f"\n📌 {type_name} ({entity_type}):")
            print(f"   Всего уникальных сущностей: {len(counter)}")
            print(f"   Всего вхождений: {len(entity_list)}")
            print(f"   Топ-{min(top_n_total, len(counter))} наиболее частотных:")

            for entity, count in counter.most_common(top_n_total):
                print(f"     - {entity} ({count})")

    print(f"\n📈 ОБЩАЯ СТАТИСТИКА:")
    total_entities = sum(len(e) for e in all_entities.values())
    unique_entities = sum(len(set(e)) for e in all_entities.values())
    print(f"   Всего уникальных сущностей: {unique_entities}")
    print(f"   Всего вхождений сущностей: {total_entities}")


def show_documents_list():
    """Показывает список всех документов для выбора"""
    documents = get_all_documents()

    if not documents:
        print("❌ Нет доступных документов")
        return None

    print(f"\n{'=' * 70}")
    print("📚 СПИСОК ДОСТУПНЫХ ДОКУМЕНТОВ")
    print(f"{'=' * 70}")
    print(f"\n{'ID':<6} {'Тип':<12} {'Название'}")
    print(f"{'─' * 70}")

    for doc_id, title, doc_type, _ in documents:
        title_short = title[:50] if title else "Без названия"
        doc_type_short = doc_type[:10] if doc_type else "Не указан"
        print(f"{doc_id:<6} {doc_type_short:<12} {title_short}")

    return documents


def interactive_search():
    """Интерактивный режим для извлечения сущностей"""
    print(f"\n{'=' * 60}")
    print("🔍 ИЗВЛЕЧЕНИЕ ИМЕНОВАННЫХ СУЩНОСТЕЙ")
    print(f"{'=' * 60}")

    print("\nВыберите режим работы:")
    print("1 - Извлечь сущности из конкретного документа")
    print("2 - Статистика сущностей по всем документам")

    choice = input("\n👉 Ваш выбор (1/2): ").strip()

    if choice == '1':
        documents = show_documents_list()
        if not documents:
            return

        while True:
            try:
                doc_id = input(f"\n👉 Введите ID документа: ").strip()
                doc_id = int(doc_id)

                doc_exists = any(doc[0] == doc_id for doc in documents)
                if doc_exists:
                    break
                else:
                    print(f"❌ Документ с ID {doc_id} не найден. Попробуйте снова.")
            except ValueError:
                print("❌ Пожалуйста, введите корректный числовой ID")
            except KeyboardInterrupt:
                print("\n👋 Отмена")
                return

        while True:
            try:
                top_n = input(f"\n👉 Введите количество сущностей для вывода (по умолчанию 20): ").strip()
                if not top_n:
                    top_n = 20
                    break
                top_n = int(top_n)
                if 1 <= top_n <= 100:
                    break
                else:
                    print("❌ Пожалуйста, введите число от 1 до 100")
            except ValueError:
                print("❌ Пожалуйста, введите корректное число")

        extract_entities_from_document(doc_id, top_n)

    elif choice == '2':
        while True:
            try:
                top_n_doc = input(
                    f"\n👉 Введите количество сущностей для вывода из каждого документа (по умолчанию 20): ").strip()
                if not top_n_doc:
                    top_n_doc = 20
                    break
                top_n_doc = int(top_n_doc)
                if 1 <= top_n_doc <= 100:
                    break
                else:
                    print("❌ Пожалуйста, введите число от 1 до 100")
            except ValueError:
                print("❌ Пожалуйста, введите корректное число")

        while True:
            try:
                top_n_total = input(
                    f"\n👉 Введите количество топ-сущностей для общей статистики (по умолчанию 30): ").strip()
                if not top_n_total:
                    top_n_total = 30
                    break
                top_n_total = int(top_n_total)
                if 1 <= top_n_total <= 100:
                    break
                else:
                    print("❌ Пожалуйста, введите число от 1 до 100")
            except ValueError:
                print("❌ Пожалуйста, введите корректное число")

        extract_entities_all_documents(top_n_doc, top_n_total)

    else:
        print("❌ Неверный выбор!")


if __name__ == "__main__":
    print("🔍 СИСТЕМА ИЗВЛЕЧЕНИЯ ИМЕНОВАННЫХ СУЩНОСТЕЙ")
    print("=" * 60)
    interactive_search()