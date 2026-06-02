-- 1. Папки (иерархия с Google Drive)
CREATE TABLE folders (
    id SERIAL PRIMARY KEY,
    gdrive_folder_id VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    parent_folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    full_path TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Документы (файлы с текстом)
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    gdrive_file_id VARCHAR(100) UNIQUE NOT NULL,
    folder_id INTEGER NOT NULL REFERENCES folders(id),
    title VARCHAR(500) NOT NULL,
    source_url TEXT, -- ссылка на файл в Google Drive
    authors TEXT[],
    original_creation_date DATE, -- из метаданных файла или из текста
    modified_time TIMESTAMP,     -- из Google Drive
    parsed_at TIMESTAMP DEFAULT NOW(),
    loaded_to_db_at TIMESTAMP DEFAULT NOW()
);

-- 3. Элементы документа (абзацы, заголовки, списки)
CREATE TABLE document_elements (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    element_type VARCHAR(20) CHECK (element_type IN ('paragraph', 'heading', 'list')),
    content TEXT NOT NULL,
    position_order INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. Изображения
CREATE TABLE images (
    id SERIAL PRIMARY KEY,
    gdrive_file_id VARCHAR(100) UNIQUE NOT NULL,
    original_url TEXT NOT NULL,
    local_path VARCHAR(500),
    folder_id INTEGER REFERENCES folders(id),
    document_id INTEGER REFERENCES documents(id),
    caption TEXT,
    modified_time TIMESTAMP,
    extracted_at TIMESTAMP DEFAULT NOW()
);

-- 5. Метаданные документа (гибкие поля)
CREATE TABLE document_metadata (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    meta_key VARCHAR(100) NOT NULL,
    meta_value TEXT,
    UNIQUE(document_id, meta_key)
);

-- 6. (Задел для Егора) Леммы
CREATE TABLE lemmas (
    id SERIAL PRIMARY KEY,
    lemma VARCHAR(255) NOT NULL,
    word_form VARCHAR(255),
    document_element_id INTEGER REFERENCES document_elements(id) ON DELETE CASCADE,
    position_in_element INTEGER
);

-- 7. (Задел для Егора) Именованные сущности
CREATE TABLE named_entities (
    id SERIAL PRIMARY KEY,
    entity_text VARCHAR(500) NOT NULL,
    entity_type VARCHAR(50), -- PERSON, DATE, ORG, GPE и т.д.
    document_element_id INTEGER REFERENCES document_elements(id) ON DELETE CASCADE,
    start_pos INTEGER,
    end_pos INTEGER
);