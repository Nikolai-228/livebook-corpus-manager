# postprocessing/topic_modeling.py
"""
Тематическое моделирование с использованием BERTopic
Использует лемматизированные тексты из таблицы documents_lemmatized
Модель: paraphrase-multilingual-mpnet-base-v2
"""

import sys
import re
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from tqdm import tqdm

# BERTopic и зависимости
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer

try:
    from postprocessing.config import DATABASE_DSN, PROJECT_ROOT
except ImportError:
    from config import DATABASE_DSN, PROJECT_ROOT

# ==========================================================
# 1. КОНФИГУРАЦИЯ
# ==========================================================

# Параметры модели
N_TOPICS = 20  # Желаемое количество тем
RANDOM_STATE = 42  # Для воспроизводимости

# Настройки для работы на CPU
UMAP_COMPONENTS = 5  # Меньше компонентов = быстрее на CPU
HDBSCAN_MIN_CLUSTER_SIZE = 5  # Минимальный размер кластера

# Режимы работы
TEST_MODE = True  # True - только первые N документов, False - все
TEST_LIMIT = 100  # Количество документов для теста

# Настройки логирования
LOG_FILE = PROJECT_ROOT / "logs" / "topic_modeling.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==========================================================
# 2. ЗАГРУЗКА ДАННЫХ ИЗ БД
# ==========================================================

def get_db_connection():
    """Создаёт подключение к PostgreSQL"""
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_DSN)

    conn = psycopg2.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname or 'localhost',
        port=parsed.port or 5432,
        database=parsed.path[1:] if parsed.path else 'livebook_corpus'
    )
    return conn


def load_lemmatized_documents(limit=None):
    """
    Загружает лемматизированные тексты из таблицы documents_lemmatized

    Args:
        limit: ограничение на количество документов (для теста)

    Returns:
        tuple: (doc_ids, lemmatized_texts, original_titles)
    """
    logger.info("📚 ЗАГРУЗКА ЛЕММАТИЗИРОВАННЫХ ДОКУМЕНТОВ ИЗ БД...")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Загружаем документы из таблицы documents_lemmatized
    query = """
        SELECT 
            dl.id_documents,
            dl.content as lemmatized_text,
            d.title,
            d.type,
            d.chapter_id
        FROM documents_lemmatized dl
        JOIN documents d ON d.id = dl.id_documents
        WHERE dl.content IS NOT NULL 
          AND dl.content != ''
          AND dl.total_tokens_count > 30
        ORDER BY dl.id_documents
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    results = cursor.fetchall()

    doc_ids = [row[0] for row in results]
    lemmatized_texts = [row[1] for row in results]
    titles = [row[2] for row in results]
    types = [row[3] for row in results]
    chapter_ids = [row[4] for row in results]

    cursor.close()
    conn.close()

    logger.info(f"   ✅ Загружено документов: {len(lemmatized_texts)}")
    if len(lemmatized_texts) > 0:
        logger.info(
            f"   📊 Средняя длина текста: {sum(len(t) for t in lemmatized_texts) / len(lemmatized_texts):.0f} символов")

    return doc_ids, lemmatized_texts, titles, types, chapter_ids


# ==========================================================
# 3. НАСТРОЙКА МОДЕЛИ BERTopic
# ==========================================================

def setup_bertopic_model(n_topics=N_TOPICS, n_documents=100):
    """
    Настраивает и возвращает модель BERTopic с параметрами
    для работы на CPU с русским языком.

    Args:
        n_topics: количество тем
        n_documents: количество документов (для настройки векторизатора)
    """
    logger.info("⚙️ НАСТРОЙКА МОДЕЛИ BERTopic...")
    logger.info(f"   Модель эмбеддингов: paraphrase-multilingual-mpnet-base-v2")
    logger.info(f"   Количество тем: {n_topics}")

    # 1. Эмбеддер с русской поддержкой
    embedding_model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    logger.info("   ✅ Эмбеддер загружен")

    # 2. UMAP для снижения размерности (оптимизация для CPU)
    umap_model = UMAP(
        n_neighbors=15,
        n_components=UMAP_COMPONENTS,
        min_dist=0.0,
        metric='cosine',
        random_state=RANDOM_STATE,
        low_memory=True,
        verbose=False
    )
    logger.info(f"   ✅ UMAP настроен (n_components={UMAP_COMPONENTS})")

    # 3. HDBSCAN для кластеризации
    if n_documents < 50:
        min_cluster_size = 2
    elif n_documents < 200:
        min_cluster_size = 3
    else:
        min_cluster_size = HDBSCAN_MIN_CLUSTER_SIZE

    hdbscan_model = HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric='euclidean',
        cluster_selection_epsilon=0.0,
        prediction_data=True,
        gen_min_span_tree=True,
        core_dist_n_jobs=1
    )
    logger.info(f"   ✅ HDBSCAN настроен (min_cluster_size={min_cluster_size})")

    # 4. Векторизатор для извлечения ключевых слов
    if n_documents < 50:
        vectorizer_model = CountVectorizer(
            ngram_range=(1, 2),
            stop_words=None,
            min_df=1,
            max_df=0.95
        )
    elif n_documents < 200:
        vectorizer_model = CountVectorizer(
            ngram_range=(1, 2),
            stop_words=None,
            min_df=1,
            max_df=0.9
        )
    else:
        vectorizer_model = CountVectorizer(
            ngram_range=(1, 2),
            stop_words=None,
            min_df=2,
            max_df=0.8
        )
    logger.info(f"   ✅ Векторизатор настроен (min_df={vectorizer_model.min_df}, max_df={vectorizer_model.max_df})")

    # 5. Создаем модель
    topic_model = BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        language="russian",
        calculate_probabilities=False,
        verbose=False,
        low_memory=True
    )
    logger.info("   ✅ Модель BERTopic создана")

    return topic_model


# ==========================================================
# 4. ОБУЧЕНИЕ МОДЕЛИ
# ==========================================================

def train_topic_model(topic_model, texts, doc_ids):
    """
    Обучает модель BERTopic на текстах

    Args:
        topic_model: модель BERTopic
        texts: список текстов
        doc_ids: список ID документов

    Returns:
        tuple: (topics, probabilities)
    """
    logger.info("🔄 ОБУЧЕНИЕ МОДЕЛИ BERTopic...")
    logger.info(f"   Количество документов: {len(texts)}")
    logger.info("   ⏳ Это может занять несколько минут...")

    start_time = datetime.now()

    try:
        topics, probs = topic_model.fit_transform(texts)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"   ✅ Обучение завершено за {elapsed:.2f} секунд")

        unique_topics = set(topics)
        n_clusters = len([t for t in unique_topics if t != -1])
        n_noise = sum(1 for t in topics if t == -1)

        logger.info(f"   📊 Количество кластеров: {n_clusters}")
        if len(topics) > 0:
            logger.info(
                f"   📊 Количество документов вне кластеров (-1): {n_noise} ({n_noise / len(topics) * 100:.1f}%)")

        return topics, probs

    except Exception as e:
        logger.error(f"❌ Ошибка при обучении модели: {e}")
        logger.info("   🔄 Пробуем с альтернативными настройками...")

        from umap import UMAP
        umap_model = UMAP(
            n_neighbors=5,
            n_components=3,
            min_dist=0.0,
            metric='cosine',
            random_state=RANDOM_STATE,
            low_memory=True,
            verbose=False
        )

        topic_model.umap_model = umap_model
        topics, probs = topic_model.fit_transform(texts)

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"   ✅ Обучение (альтернативное) завершено за {elapsed:.2f} секунд")

        return topics, probs


# ==========================================================
# 5. СОХРАНЕНИЕ РЕЗУЛЬТАТОВ В БД
# ==========================================================

def ensure_topic_id_column(conn):
    """
    Проверяет и добавляет поле topic_id в таблицу documents, если его нет
    """
    cursor = conn.cursor()

    # Проверяем, существует ли поле topic_id
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'documents' AND column_name = 'topic_id'
    """)

    if not cursor.fetchone():
        logger.info("   Добавление поля topic_id в таблицу documents...")
        cursor.execute("ALTER TABLE documents ADD COLUMN topic_id INTEGER")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_topic_id ON documents(topic_id)")
        conn.commit()
        logger.info("   ✅ Поле topic_id добавлено")
        return True
    return False


def create_topics_table(conn):
    """
    Создает таблицу topics_summary с одним полем id
    """
    cursor = conn.cursor()

    # Создаем таблицу topics_summary с id как PRIMARY KEY
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics_summary (
            id INTEGER PRIMARY KEY,  -- это и есть topic_id (начинается с 1)
            name VARCHAR(500),
            keywords TEXT,
            doc_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    logger.info("   ✅ Таблица topics_summary создана/проверена")


def save_topics_to_db(conn, doc_ids, topics, topic_model):
    """
    Сохраняет темы в БД:
    1. Обновляет поле topic_id в таблице documents (topic_id + 1)
    2. Сохраняет описания тем в таблицу topics_summary с id = topic_id + 1
    """
    logger.info("\n💾 СОХРАНЕНИЕ ТЕМ В БД...")

    cursor = conn.cursor()

    # 1. Убеждаемся, что поле topic_id существует
    ensure_topic_id_column(conn)

    # 2. Убеждаемся, что таблица topics_summary существует
    create_topics_table(conn)

    # 3. Очищаем старые данные
    logger.info("   Очистка таблицы topics_summary...")
    cursor.execute("TRUNCATE TABLE topics_summary")
    conn.commit()
    logger.info("   ✅ Таблица topics_summary очищена")

    # 4. Сохраняем описания тем
    logger.info("   Сохранение описаний тем...")
    topic_info = topic_model.get_topic_info()

    for _, row in topic_info.iterrows():
        # topic_id из модели (начинается с -1, 0, 1, 2...)
        model_topic_id = row['Topic']
        name = row['Name']
        count = row['Count']

        # Преобразуем: для topic_id >= 0 добавляем +1, чтобы начинались с 1
        # Для topic_id == -1 оставляем -1 (мусорная тема)
        if model_topic_id >= 0:
            display_topic_id = model_topic_id + 1
        else:
            display_topic_id = -1

        # Очищаем название: убираем первую цифру и подчеркивание после нее
        clean_name = name
        if clean_name:
            clean_name = re.sub(r'^\d+_', '', clean_name)
            if not clean_name or clean_name.strip() == '':
                clean_name = f"Тема {display_topic_id}"

        # Получаем ключевые слова для темы
        if model_topic_id != -1:
            words = topic_model.get_topic(model_topic_id)
            keywords = ', '.join([f"{word[0]}" for word in words[:10]]) if words else ""
        else:
            keywords = "Документы без четкой темы"

        # Сохраняем с display_topic_id как PRIMARY KEY (поле id)
        cursor.execute("""
            INSERT INTO topics_summary (id, name, keywords, doc_count)
            VALUES (%s, %s, %s, %s)
        """, (display_topic_id, clean_name, keywords, count))

    conn.commit()
    logger.info(f"   ✅ Сохранено {len(topic_info)} тем в topics_summary")

    # 5. Обновляем документы (поле topic_id)
    logger.info("   Обновление документов...")
    updated_count = 0

    for doc_id, model_topic_id in zip(doc_ids, topics):
        if model_topic_id >= 0:
            display_topic_id = model_topic_id + 1
        else:
            display_topic_id = -1

        cursor.execute("""
            UPDATE documents 
            SET topic_id = %s 
            WHERE id = %s
        """, (display_topic_id, doc_id))
        updated_count += 1

        if updated_count % 100 == 0:
            conn.commit()
            logger.info(f"   Обновлено {updated_count} документов...")

    conn.commit()
    logger.info(f"   ✅ Обновлено {updated_count} документов (поле topic_id)")

    # 6. Выводим пример для проверки
    logger.info("\n📋 ПРИМЕР СОХРАНЕННЫХ ТЕМ:")
    logger.info("-" * 70)
    cursor.execute("""
        SELECT id, name, doc_count 
        FROM topics_summary 
        WHERE id != -1
        ORDER BY id 
        LIMIT 10
    """)
    examples = cursor.fetchall()
    for topic_id, name, count in examples:
        logger.info(f"   Тема {topic_id}: {name} (документов: {count})")

# ==========================================================
# 6. АНАЛИЗ РЕЗУЛЬТАТОВ
# ==========================================================

def analyze_topics(topic_model, topics, doc_ids, titles):
    """
    Анализирует и выводит информацию о темах
    """
    logger.info("\n" + "=" * 70)
    logger.info("📊 АНАЛИЗ ТЕМ")
    logger.info("=" * 70)

    # Получаем информацию о темах
    topic_info = topic_model.get_topic_info()
    logger.info(f"\n📋 Информация о темах:")
    logger.info(topic_info.to_string())

    # Выводим топ-10 тем
    logger.info("\n🏆 ТОП-10 ТЕМ:")
    logger.info("-" * 70)

    for i, row in topic_info.head(10).iterrows():
        topic_id = row['Topic']
        count = row['Count']
        name = row['Name']
        logger.info(f"   Тема {topic_id}: {name} (документов: {count})")

        # Показываем ключевые слова для темы
        if topic_id != -1:  # -1 это "мусорная" тема
            words = topic_model.get_topic(topic_id)
            if words:
                top_words = ', '.join([f"{word[0]}" for word in words[:5]])
                logger.info(f"      Ключевые слова: {top_words}")

    # Статистика распределения тем по документам
    if len(topics) > 0:
        logger.info("\n📊 СТАТИСТИКА РАСПРЕДЕЛЕНИЯ ТЕМ:")
        logger.info("-" * 70)

        # Считаем документы по темам
        topic_counts = {}
        for t in topics:
            topic_counts[t] = topic_counts.get(t, 0) + 1

        # Выводим статистику
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        for topic_id, count in sorted_topics[:10]:
            if topic_id == -1:
                topic_name = "Мусорная тема (без кластера)"
            else:
                try:
                    topic_name = topic_model.get_topic_info().loc[
                        topic_model.get_topic_info()['Topic'] == topic_id, 'Name'
                    ].values[0]
                except:
                    topic_name = f"Тема {topic_id}"
            logger.info(f"   Тема {topic_id}: {count} документов ({count / len(topics) * 100:.1f}%)")


# ==========================================================
# 7. ОСНОВНАЯ ФУНКЦИЯ
# ==========================================================

def run_topic_modeling(limit=None, save_to_db=True, n_topics=N_TOPICS):
    """
    Запускает процесс тематического моделирования

    Args:
        limit: ограничение на количество документов (для теста)
        save_to_db: сохранять ли результаты в БД
        n_topics: количество тем
    """
    logger.info("=" * 70)
    logger.info("🚀 ТЕМАТИЧЕСКОЕ МОДЕЛИРОВАНИЕ С BERTopic")
    logger.info("   Модель: paraphrase-multilingual-mpnet-base-v2")
    logger.info(f"   Количество тем: {n_topics}")
    if limit:
        logger.info(f"   Режим: ТЕСТ (первые {limit} документов)")
    logger.info("=" * 70)

    # 1. Загружаем данные
    doc_ids, texts, titles, types, chapter_ids = load_lemmatized_documents(limit=limit)

    if len(texts) == 0:
        logger.error("❌ Нет документов для обработки")
        return

    # 2. Настраиваем модель (передаем количество документов для настройки)
    topic_model = setup_bertopic_model(n_topics=n_topics, n_documents=len(texts))

    # 3. Обучаем модель
    topics, probs = train_topic_model(topic_model, texts, doc_ids)

    # 4. Анализируем результаты
    analyze_topics(topic_model, topics, doc_ids, titles)

    # 5. Сохраняем в БД
    if save_to_db:
        try:
            conn = get_db_connection()

            # Сохраняем темы
            save_topics_to_db(conn, doc_ids, topics, topic_model)

            conn.close()
            logger.info("\n✅ Результаты сохранены в БД")

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения в БД: {e}")
            import traceback
            traceback.print_exc()

    # 6. Сохраняем модель в файл
    try:
        # Сохраняем модель
        model_dir = PROJECT_ROOT / "models" / "bertopic"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"bertopic_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Сохраняем модель
        topic_model.save(str(model_path))
        logger.info(f"   💾 Модель сохранена в: {model_path}")
    except Exception as e:
        logger.warning(f"   ⚠️ Не удалось сохранить модель: {e}")

    logger.info("\n✅ ТЕМАТИЧЕСКОЕ МОДЕЛИРОВАНИЕ ЗАВЕРШЕНО!")


# ==========================================================
# 8. ТОЧКА ВХОДА
# ==========================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Тематическое моделирование с BERTopic')
    parser.add_argument('--test', '-t', action='store_true', help='Тестовый запуск (первые 100 документов)')
    parser.add_argument('--limit', '-l', type=int, help='Ограничить количество документов')
    parser.add_argument('--no-save', '-n', action='store_true', help='Не сохранять результаты в БД')
    parser.add_argument('--topics', '-k', type=int, default=N_TOPICS, help=f'Количество тем (по умолчанию: {N_TOPICS})')

    args = parser.parse_args()

    # Определяем лимит
    limit = None
    if args.test:
        limit = TEST_LIMIT
        logger.info("⚠️ ТЕСТОВЫЙ РЕЖИМ")
    elif args.limit:
        limit = args.limit

    # Запускаем моделирование
    run_topic_modeling(
        limit=limit,
        save_to_db=not args.no_save,
        n_topics=args.topics
    )


if __name__ == "__main__":
    main()