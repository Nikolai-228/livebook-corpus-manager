-- Только если нет хостинга!
CREATE DATABASE livebook_corpus
    WITH
    OWNER = your_username
    ENCODING = 'UTF8'
    CONNECTION LIMIT = -1;

-- Подключение к базе данных (если создаёте отдельно)
\c livebook_corpus;

-- =====================================================
-- Таблица chapters (родительская)
-- =====================================================
CREATE TABLE chapters (
    id SERIAL PRIMARY KEY,
    name character varying(255) NOT NULL
);

-- =====================================================
-- Таблица folders (самореферентная, ссылается сама на себя)
-- =====================================================
CREATE TABLE folders (
    id SERIAL PRIMARY KEY,
    name character varying(1000) NOT NULL,
    parent_folder_id integer,
    full_path text,
    chapter_id integer,
    created_at timestamp without time zone DEFAULT now()
);

-- Индексы для folders
CREATE INDEX idx_folders_chapter ON folders (chapter_id);
CREATE INDEX idx_folders_parent ON folders (parent_folder_id);

-- =====================================================
-- Таблица documents (ссылается на chapters и folders)
-- =====================================================
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title character varying(1000) NOT NULL,
    chapter_id integer NOT NULL,
    folder_id integer,
    content text,
    url text,
    creation_date date,
    type character varying(50)
);

-- =====================================================
-- Таблица media (ссылается на chapters, folders, documents)
-- =====================================================
CREATE TABLE media (
    id SERIAL PRIMARY KEY,
    chapter_id integer NOT NULL,
    folder_id integer,
    document_id integer,
    name character varying(500),
    media bytea
);

-- =====================================================
-- Добавление внешних ключей (после создания всех таблиц)
-- =====================================================

-- Внешние ключи для таблицы folders
ALTER TABLE folders
    ADD CONSTRAINT folders_chapter_id_fkey
    FOREIGN KEY (chapter_id) REFERENCES chapters(id);

ALTER TABLE folders
    ADD CONSTRAINT folders_parent_folder_id_fkey
    FOREIGN KEY (parent_folder_id) REFERENCES folders(id) ON DELETE CASCADE;

-- Внешние ключи для таблицы documents
ALTER TABLE documents
    ADD CONSTRAINT documents_chapter_id_fkey
    FOREIGN KEY (chapter_id) REFERENCES chapters(id);

-- Внешние ключи для таблицы media
ALTER TABLE media
    ADD CONSTRAINT media_chapter_id_fkey
    FOREIGN KEY (chapter_id) REFERENCES chapters(id);

ALTER TABLE media
    ADD CONSTRAINT media_document_id_fkey
    FOREIGN KEY (document_id) REFERENCES documents(id);
