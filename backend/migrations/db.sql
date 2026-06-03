CREATE TABLE chapters (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2.2 Таблица папок (folders)
CREATE TABLE folders (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    parent_folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
    full_path TEXT,
    chapter_id INTEGER REFERENCES chapters(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2.3 Таблица документов (documents)
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    type VARCHAR(50),  -- pdf, docx, txt, google_doc, doc, other
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    content TEXT,
    url TEXT,
    creation_date DATE,
    parsed_at TIMESTAMP DEFAULT NOW(),
    loaded_to_db_at TIMESTAMP DEFAULT NOW()
);

-- 2.4 Таблица медиафайлов (media) - изображения и видео
CREATE TABLE media (
    id SERIAL PRIMARY KEY,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    folder_id INTEGER REFERENCES folders(id) ON DELETE SET NULL,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    name TEXT,
    media BYTEA,  -- бинарные данные изображения
    extracted_at TIMESTAMP DEFAULT NOW()
);
