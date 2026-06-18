# 📘 README: Система поиска по корпусу документов

## Что сделано

Я создал **оптимизированную систему поиска** по корпусу документов. Все ключевые данные **предварительно вычислены** и хранятся в БД, что делает поиск **мгновенным** (без пересчёта на лету).

**Главный принцип:** данные считаются **один раз** при заполнении таблиц, поиск — это просто **SQL-запросы** к готовым таблицам.

---

## 📊 Созданные таблицы

| Таблица | Назначение | Метрика |
|---------|------------|---------|
| `collocations` | Коллокации (прил+сущ) | **Likelihood Ratio** |
| `new_bigrams` | Биграммы по частоте | **Частота** |
| `unigrams` | Униграммы | **TF*ICTF** |
| `trigrams` | Триграммы по частоте | **Частота** |
| `rake_keywords` | Ключевые фразы | **RAKE** |

**Важно:** Все таблицы заполняются из `documents_lemmatized.content` (леммы через пробел). Дополнительная лемматизация в скриптах поиска **не нужна** — используйте готовые таблицы.

---

## 🔧 Скрипты для заполнения таблиц (ЗАПУСКАЮТСЯ ОДИН РАЗ)

| Скрипт | Создаёт | Что делает |
|--------|---------|------------|
| `build_collocations.py` | `collocations` | Топ-10 коллокаций по Likelihood Ratio на документ |
| `build_bigrams.py` | `new_bigrams` | Топ-10 биграмм по частоте на документ |

**Запуск: как пример**
```bash
python build_collocations.py     # потом (один раз) уже запущенно, то есть таблицы заполнены
python build_bigrams.py          # потом (один раз)
```

---

## 🔍 Скрипты поиска (ГОТОВЫ К ИСПОЛЬЗОВАНИЮ)

| Скрипт | Что ищет | Где | Использует таблицу |
|--------|----------|-----|-------------------|
| `search_collocations.py` | Коллокации (Likelihood) | Документ | `collocations` |
| `search_bigrams_by_word.py` | Биграммы по слову | Документ / Раздел | `new_bigrams` |
| `maska.py` | Регулярные выражения | Оригинал / Леммы | `documents.content` / `documents_lemmatized.content` |

Эти скрипты **используют готовые таблицы** и работают быстро. **Никакой повторной лемматизации или пересчёта n-грамм!**

---

## ⚠️ Что нужно ПЕРЕДЕЛАТЬ 

Ты(Егор) написал скрипты, которые **лемматизируют на лету** и **пересчитывают n-граммы при каждом поиске**. Это **медленно и неправильно**. Их нужно переписать по единому принципу:

### 🔴 Проблема всех старых скриптов:
```python
# ❌ НЕПРАВИЛЬНО: лемматизация на лету
morph = MorphAnalyzer()
lemmas = preprocess_text(content, morph)  # дорого и медленно

# ❌ НЕПРАВИЛЬНО: пересчёт n-грамм при каждом поиске
finder = BigramCollocationFinder.from_words(lemmas)
scored = finder.score_ngrams(BigramAssocMeasures.likelihood_ratio)
```

### ✅ КАК ДОЛЖНО БЫТЬ:
```python
# ✅ ПРАВИЛЬНО: простой SQL-запрос к готовой таблице
cur.execute("""
    SELECT id_documents, bigram, frequency, contexts
    FROM new_bigrams
    WHERE word1 = %s OR word2 = %s
""", (search_lemma, search_lemma))
```

---

### 1. `rake_search.py` — нужно переделать

**Проблема:** 
- Лемматизирует заново
- Не использует таблицу `rake_keywords`

**Как исправить:**
```python
# Вместо вычислений на лету — простой запрос к таблице
def search_rake_by_keyword(keyword, doc_id=None):
    conn = connect_db()
    cur = conn.cursor()
    
    # Лемматизируем ТОЛЬКО поисковое слово (один раз)
    search_lemma = get_lemma(keyword)
    
    # Ищем в готовой таблице
    cur.execute("""
        SELECT id_documents, keyword, score, contexts
        FROM rake_keywords
        WHERE keyword LIKE %s
    """, (f'%{search_lemma}%',))
    
    results = cur.fetchall()
    # ... вывод результатов
```

**Для TF*ICTF:** используй поле `tf_idf_score` в таблице `unigrams` — там уже посчитан TF*ICTF.

---

### 2. `search.py` — нужно переделать

**Проблема:** 
- Универсальный, но внутри пересчитывает n-граммы
- Не использует готовые таблицы

**Как исправить:**
```python
# Вместо вычислений на лету:
def search_unigrams(search_word, doc_id=None):
    search_lemma = get_lemma(search_word)
    
    # ✅ Простой запрос к таблице unigrams
    cur.execute("""
        SELECT id_documents, unigram, frequency, tf_idf_score, contexts
        FROM unigrams
        WHERE unigram = %s
    """, (search_lemma,))
    
    # Для биграмм — таблица new_bigrams
    # Для триграмм — таблица trigrams
    # Для RAKE — таблица rake_keywords
```

---

### 3. `trigrams_search.py` — нужно переделать

**Проблема:** вычисляет триграммы на лету

**Как исправить:**
```python
def search_trigrams_by_word(search_word, doc_id=None):
    search_lemma = get_lemma(search_word)
    
    cur.execute("""
        SELECT id_documents, trigram, frequency, contexts
        FROM trigrams
        WHERE trigram LIKE %s
    """, (f'%{search_lemma}%',))
    
    # ... вывод результатов
```

---

### 4. `unigrams_search.py` — нужно переделать

**Проблема:**
- Ошибка в SQL (`INNER JOIN content` вместо `documents_lemmatized`)
- Лемматизация на лету

**Как исправить:**
```python
def search_unigrams_by_word(search_word, doc_id=None):
    search_lemma = get_lemma(search_word)
    
    cur.execute("""
        SELECT id_documents, unigram, frequency, tf_idf_score, contexts
        FROM unigrams
        WHERE unigram = %s
    """, (search_lemma,))
```



---

## ✅ Что МОЖНО ОСТАВИТЬ (без изменений)

| Скрипт | Почему |
|--------|--------|
| `imen.py` | NER на оригинальном тексте — не требует лемм |
| `maska.py` | Регулярные выражения — работает с любым текстом |
| `documents_lemmatized.py` | Создаёт базу для всех остальных (уже готов) |
| `build_collocations.py` | ✅ готов |
| `build_bigrams.py` | ✅ готов |
| `search_collocations.py` | ✅ готов |
| `search_bigrams_by_word.py` | ✅ готов |

---

## 📌 ТЗ для коллеги (кратко)

1. **Переделать** `rake_search.py`, `search.py`, `trigrams_search.py`, `unigrams_search.py` 
2. **Использовать только TF*ICTF** для униграмм (поле `tf_idf_score` в `unigrams`)
3. **НЕ лемматизировать** документы заново — бери леммы из `documents_lemmatized.content`
4. **НЕ пересчитывать** n-граммы на лету — используй готовые таблицы
5. **Поиск = SQL-запрос** к готовой таблице. Всё.
6. **Пример правильного подхода** — смотри `search_bigrams_by_word.py`
7. **С биграммами вроде больше ниче делать не надо, есть поиск коллокаций просто биграмм(в итоге разница только в том что первые по лайклихуд
8. ищутся а вторые по частоте) по слову биграмму искать я тоже переделал**
---



---

## 📞 Вопросы

Если что-то непонятно — спрашивай. 

**Главное правило:** данные считаются один раз при заполнении таблиц. Поиск — это просто SQL-запрос к готовым данным. Никакой лемматизации и пересчёта во время поиска!
