Вот обновлённый `README.md` для твоего модуля парсинга:

```markdown
# Модуль парсинга Google Drive

Модуль для автоматического извлечения, обработки и загрузки в базу данных PostgreSQL документов и изображений из Google Drive. Входит в состав проекта **«Живая книга ИМИ — Корпусный менеджер»**.

---

## 📋 Назначение

Модуль обеспечивает:
- Рекурсивный обход структуры папок Google Drive
- Извлечение текста из документов различных форматов
- Распознавание текста в PDF-файлах (с использованием PyMuPDF)
- Извлечение изображений из HTML, DOCX и Google Docs
- Сохранение данных в структурированную базу данных PostgreSQL
- **Два режима работы:** полная перезапись или продолжение с того же места

---

## 📁 Структура модуля

```
parser/

├── config.py                          # Конфигурация: API-ключи, разделы, БД

├── db_utils.py                        # Утилиты для работы с PostgreSQL

├── text_extractor.py                  # Извлечение текста и изображений из файлов

├── parse_all_chapters_clean.py        # Полная перезапись БД

├── parse_all_chapters_continue.py     # Продолжение (только новые файлы)

└── livebook-parser-265c1e8112e9.json  # Ключ сервисного аккаунта Google
```

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib beautifulsoup4 psycopg2-binary PyMuPDF requests
```

> **Важно:** `kreuzberg` больше не используется.

### 2. Создание базы данных

Выполни `schema.sql` в своей БД (файл находится в модуле create_db):

```bash
psql -U postgres -c "CREATE DATABASE livebook_corpus;"
psql -U postgres -d livebook_corpus -f schema.sql
```

Или создай вручную для дальнейшего автоматического создания всех таблиц, 
связей индексов и тд (не рекомендовано):

```sql
CREATE DATABASE livebook_corpus;
```

### 3. Настройка подключения к БД

Отредактируй `config.py`:

```python
# PostgreSQL
DATABASE_DSN = "postgresql://postgres:password@localhost:5432/livebook_corpus"
```

Формат: `postgresql://user:password@host:port/database`

### 4. Настройка Google Drive

## 🔐 Создание ключа сервисного аккаунта Google

1. Перейди в [Google Cloud Console](https://console.cloud.google.com/)
2. Создай новый проект или выбери существующий
3. Включи **Google Drive API**
4. Перейди в **IAM & Admin → Service Accounts**
5. Нажми **+ CREATE SERVICE ACCOUNT**
6. Укажи имя → **CREATE AND CONTINUE** → **DONE**
7. Нажми на созданный аккаунт → **KEYS** → **ADD KEY** → **Create New Key**
8. Выбери **JSON** → ключ скачается автоматически
9. Перемести файл в папку `parser/`
10. В `config.py` укажи путь к файлу:

```python
SERVICE_ACCOUNT_FILE = r'путь\к\папке\parser\название_ключа.json'
```
Или запроси файл с ключом у автора модуля, не рекомендовано размещать 
ключ API в открытых источниках.

### 5. Запуск

**Полная перезапись** (удаляет все старые данные):

```bash
python parse_all_chapters_clean.py
```

**Продолжение** (добавляет только новые файлы):

```bash
python parse_all_chapters_continue.py
```

---

## 🔧 Два режима работы

| Режим | Скрипт | Что делает |
|-------|--------|------------|
| **Полная перезапись** | `parse_all_chapters_clean.py` | 🗑️ Удаляет все данные из `chapters`, `folders`, `documents`, `media` и заполняет заново |
| **Продолжение** | `parse_all_chapters_continue.py` | ➕ Добавляет только новые файлы, пропускает уже существующие (по `url`) |

---

## ⚙️ Конфигурация

### `config.py`

| Переменная | Назначение |
|------------|------------|
| `SERVICE_ACCOUNT_FILE` | Путь к JSON-ключу сервисного аккаунта Google |
| `CHAPTERS` | Список словарей с названиями и ID папок разделов |
| `DATABASE_DSN` | Строка подключения к PostgreSQL |

Пример `CHAPTERS`:

```python
CHAPTERS = [
    {"name": "Выпуск 1962", "folder_id": "0B8SHLgKhSzzVQkJlTmlZTTA3VlU"},
    {"name": "Стройотряды", "folder_id": "0B7oIjQ46Neu2b0poX0JQVE9iZ1E"},
    # ...
]
```

---

## 🧠 Особенности обработки

### Текст

| Формат | Метод |
|--------|-------|
| **PDF** | PyMuPDF (`fitz`) с очисткой от номеров страниц, сносок, ссылок |
| **DOCX** | Распаковка `zip` и чтение `word/document.xml` |
| **Google Docs** | Экспорт в HTML → BeautifulSoup → очистка |
| **TXT** | Прямое чтение |
| **DOC (старый)** | Чтение как plain text |

### Изображения

| Источник | Метод |
|----------|-------|
| HTML / Google Docs | Извлечение из `data:` URI и внешних URL |
| DOCX | Распаковка `word/media/` |
| Отдельные файлы | Скачивание через Drive API |

---

## 📊 Схема данных

Модуль оперирует четырьмя таблицами:

```
chapters (id, name)
    ├── folders (id, name, parent_folder_id, full_path, chapter_id)
    ├── documents (id, title, type, chapter_id, folder_id, content, url)
    └── media (id, chapter_id, folder_id, document_id, name, media)
```

---


## ⚙️ Требования

- Python 3.8+
- PostgreSQL 12+
- Сервисный аккаунт Google с включённым Drive API

---

## 🐛 Возможные проблемы и решения

| Проблема | Решение |
|----------|---------|
| `No module named 'tools'` | Удали `kreuzberg`: `pip uninstall kreuzberg` |
| `module 'fitz' has no attribute 'open'` | Установи PyMuPDF: `pip install PyMuPDF` |
| Ошибка подключения к БД | Проверь `DATABASE_DSN` в `config.py` |
| Сервисный аккаунт не имеет доступа | Добавь email сервисного аккаунта в права папки на Google Drive |

---

**Автор модуля:** Дресвянников Николай (nikolaj192005@mail.ru) 
**Проект:** [livebook-corpus-manager](https://github.com/Nikolai-228/livebook-corpus-manager)
```