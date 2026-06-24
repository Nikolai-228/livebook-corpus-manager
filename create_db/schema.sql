--
-- PostgreSQL database dump
--

\restrict sByxz3k0aZAHBamajNYPS7xbXWxseRex58M7r6R4d4vDX0042dfz75mnVKnqz1a

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

-- Started on 2026-06-25 00:30:57

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 220 (class 1259 OID 17056)
-- Name: chapters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.chapters (
    id integer NOT NULL,
    name character varying(255) NOT NULL
);


ALTER TABLE public.chapters OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 17055)
-- Name: chapters_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.chapters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.chapters_id_seq OWNER TO postgres;

--
-- TOC entry 5037 (class 0 OID 0)
-- Dependencies: 219
-- Name: chapters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.chapters_id_seq OWNED BY public.chapters.id;


--
-- TOC entry 222 (class 1259 OID 17081)
-- Name: documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.documents (
    id integer NOT NULL,
    title character varying(1000) NOT NULL,
    chapter_id integer NOT NULL,
    folder_id integer,
    content text,
    url text,
    type character varying(50),
    date date,
    date_uploaded date,
    date_imported date DEFAULT CURRENT_DATE,
    topic_id integer
);


ALTER TABLE public.documents OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 17080)
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.documents_id_seq OWNER TO postgres;

--
-- TOC entry 5040 (class 0 OID 0)
-- Dependencies: 221
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;


--
-- TOC entry 228 (class 1259 OID 44471)
-- Name: documents_lemmatized; Type: TABLE; Schema: public; Owner: team_user
--

CREATE TABLE public.documents_lemmatized (
    id integer NOT NULL,
    id_documents integer NOT NULL,
    content text,
    unique_lemmas_count integer DEFAULT 0,
    total_tokens_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.documents_lemmatized OWNER TO team_user;

--
-- TOC entry 227 (class 1259 OID 44470)
-- Name: documents_lemmatized_id_seq; Type: SEQUENCE; Schema: public; Owner: team_user
--

CREATE SEQUENCE public.documents_lemmatized_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.documents_lemmatized_id_seq OWNER TO team_user;

--
-- TOC entry 5042 (class 0 OID 0)
-- Dependencies: 227
-- Name: documents_lemmatized_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: team_user
--

ALTER SEQUENCE public.documents_lemmatized_id_seq OWNED BY public.documents_lemmatized.id;


--
-- TOC entry 226 (class 1259 OID 33916)
-- Name: folders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.folders (
    id integer NOT NULL,
    name character varying(1000) NOT NULL,
    parent_folder_id integer,
    full_path text,
    chapter_id integer,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.folders OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 33915)
-- Name: folders_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.folders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.folders_id_seq OWNER TO postgres;

--
-- TOC entry 5044 (class 0 OID 0)
-- Dependencies: 225
-- Name: folders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.folders_id_seq OWNED BY public.folders.id;


--
-- TOC entry 224 (class 1259 OID 17103)
-- Name: media; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.media (
    id integer NOT NULL,
    chapter_id integer NOT NULL,
    folder_id integer,
    document_id integer,
    name character varying(500),
    media bytea
);


ALTER TABLE public.media OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 17102)
-- Name: media_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.media_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.media_id_seq OWNER TO postgres;

--
-- TOC entry 5047 (class 0 OID 0)
-- Dependencies: 223
-- Name: media_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.media_id_seq OWNED BY public.media.id;


--
-- TOC entry 230 (class 1259 OID 51118)
-- Name: topics_summary; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.topics_summary (
    id integer NOT NULL,
    name character varying(500),
    keywords text,
    doc_count integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.topics_summary OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 51117)
-- Name: topics_summary_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.topics_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.topics_summary_id_seq OWNER TO postgres;

--
-- TOC entry 5050 (class 0 OID 0)
-- Dependencies: 229
-- Name: topics_summary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.topics_summary_id_seq OWNED BY public.topics_summary.id;


--
-- TOC entry 4835 (class 2604 OID 17059)
-- Name: chapters id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chapters ALTER COLUMN id SET DEFAULT nextval('public.chapters_id_seq'::regclass);


--
-- TOC entry 4836 (class 2604 OID 17084)
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- TOC entry 4841 (class 2604 OID 44474)
-- Name: documents_lemmatized id; Type: DEFAULT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.documents_lemmatized ALTER COLUMN id SET DEFAULT nextval('public.documents_lemmatized_id_seq'::regclass);


--
-- TOC entry 4839 (class 2604 OID 33919)
-- Name: folders id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.folders ALTER COLUMN id SET DEFAULT nextval('public.folders_id_seq'::regclass);


--
-- TOC entry 4838 (class 2604 OID 17106)
-- Name: media id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media ALTER COLUMN id SET DEFAULT nextval('public.media_id_seq'::regclass);


--
-- TOC entry 4845 (class 2604 OID 51121)
-- Name: topics_summary id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topics_summary ALTER COLUMN id SET DEFAULT nextval('public.topics_summary_id_seq'::regclass);


--
-- TOC entry 4848 (class 2606 OID 17063)
-- Name: chapters chapters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chapters
    ADD CONSTRAINT chapters_pkey PRIMARY KEY (id);


--
-- TOC entry 4867 (class 2606 OID 44483)
-- Name: documents_lemmatized documents_lemmatized_pkey; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.documents_lemmatized
    ADD CONSTRAINT documents_lemmatized_pkey PRIMARY KEY (id);


--
-- TOC entry 4850 (class 2606 OID 17091)
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- TOC entry 4863 (class 2606 OID 33926)
-- Name: folders folders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT folders_pkey PRIMARY KEY (id);


--
-- TOC entry 4861 (class 2606 OID 17112)
-- Name: media media_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_pkey PRIMARY KEY (id);


--
-- TOC entry 4876 (class 2606 OID 51127)
-- Name: topics_summary topics_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.topics_summary
    ADD CONSTRAINT topics_summary_pkey PRIMARY KEY (id);


--
-- TOC entry 4874 (class 2606 OID 44777)
-- Name: documents_lemmatized unique_doc_id; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.documents_lemmatized
    ADD CONSTRAINT unique_doc_id UNIQUE (id_documents);


--
-- TOC entry 4851 (class 1259 OID 46014)
-- Name: idx_documents_chapter_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_chapter_id ON public.documents USING btree (chapter_id);


--
-- TOC entry 4852 (class 1259 OID 46013)
-- Name: idx_documents_content_gin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_content_gin ON public.documents USING gin (to_tsvector('russian'::regconfig, COALESCE(content, ''::text)));


--
-- TOC entry 4853 (class 1259 OID 49731)
-- Name: idx_documents_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_date ON public.documents USING btree (date);


--
-- TOC entry 4854 (class 1259 OID 49734)
-- Name: idx_documents_date_imported; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_date_imported ON public.documents USING btree (date_imported);


--
-- TOC entry 4855 (class 1259 OID 49733)
-- Name: idx_documents_date_uploaded; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_date_uploaded ON public.documents USING btree (date_uploaded);


--
-- TOC entry 4856 (class 1259 OID 46015)
-- Name: idx_documents_folder_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_folder_id ON public.documents USING btree (folder_id);


--
-- TOC entry 4857 (class 1259 OID 46016)
-- Name: idx_documents_title; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_title ON public.documents USING btree (title varchar_pattern_ops);


--
-- TOC entry 4858 (class 1259 OID 51116)
-- Name: idx_documents_topic_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_topic_id ON public.documents USING btree (topic_id);


--
-- TOC entry 4859 (class 1259 OID 46017)
-- Name: idx_documents_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_type ON public.documents USING btree (type);


--
-- TOC entry 4864 (class 1259 OID 33938)
-- Name: idx_folders_chapter; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_folders_chapter ON public.folders USING btree (chapter_id);


--
-- TOC entry 4865 (class 1259 OID 33937)
-- Name: idx_folders_parent; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_folders_parent ON public.folders USING btree (parent_folder_id);


--
-- TOC entry 4868 (class 1259 OID 46018)
-- Name: idx_lemmatized_content_gin; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_content_gin ON public.documents_lemmatized USING gin (to_tsvector('russian'::regconfig, COALESCE(content, ''::text)));


--
-- TOC entry 4869 (class 1259 OID 44489)
-- Name: idx_lemmatized_doc_id; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_doc_id ON public.documents_lemmatized USING btree (id_documents);


--
-- TOC entry 4870 (class 1259 OID 46021)
-- Name: idx_lemmatized_stats; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_stats ON public.documents_lemmatized USING btree (unique_lemmas_count, total_tokens_count);


--
-- TOC entry 4871 (class 1259 OID 46020)
-- Name: idx_lemmatized_total_tokens; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_total_tokens ON public.documents_lemmatized USING btree (total_tokens_count);


--
-- TOC entry 4872 (class 1259 OID 46019)
-- Name: idx_lemmatized_unique_lemmas; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_unique_lemmas ON public.documents_lemmatized USING btree (unique_lemmas_count);


--
-- TOC entry 4877 (class 2606 OID 17092)
-- Name: documents documents_chapter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_chapter_id_fkey FOREIGN KEY (chapter_id) REFERENCES public.chapters(id);


--
-- TOC entry 4882 (class 2606 OID 44484)
-- Name: documents_lemmatized documents_lemmatized_id_documents_fkey; Type: FK CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.documents_lemmatized
    ADD CONSTRAINT documents_lemmatized_id_documents_fkey FOREIGN KEY (id_documents) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- TOC entry 4880 (class 2606 OID 33932)
-- Name: folders folders_chapter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT folders_chapter_id_fkey FOREIGN KEY (chapter_id) REFERENCES public.chapters(id);


--
-- TOC entry 4881 (class 2606 OID 33927)
-- Name: folders folders_parent_folder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT folders_parent_folder_id_fkey FOREIGN KEY (parent_folder_id) REFERENCES public.folders(id) ON DELETE CASCADE;


--
-- TOC entry 4878 (class 2606 OID 17113)
-- Name: media media_chapter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_chapter_id_fkey FOREIGN KEY (chapter_id) REFERENCES public.chapters(id);


--
-- TOC entry 4879 (class 2606 OID 17123)
-- Name: media media_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- TOC entry 5035 (class 0 OID 0)
-- Dependencies: 5
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT ALL ON SCHEMA public TO team_user;


--
-- TOC entry 5036 (class 0 OID 0)
-- Dependencies: 220
-- Name: TABLE chapters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.chapters TO team_user;


--
-- TOC entry 5038 (class 0 OID 0)
-- Dependencies: 219
-- Name: SEQUENCE chapters_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.chapters_id_seq TO team_user;


--
-- TOC entry 5039 (class 0 OID 0)
-- Dependencies: 222
-- Name: TABLE documents; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.documents TO team_user;


--
-- TOC entry 5041 (class 0 OID 0)
-- Dependencies: 221
-- Name: SEQUENCE documents_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.documents_id_seq TO team_user;


--
-- TOC entry 5043 (class 0 OID 0)
-- Dependencies: 226
-- Name: TABLE folders; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.folders TO team_user;


--
-- TOC entry 5045 (class 0 OID 0)
-- Dependencies: 225
-- Name: SEQUENCE folders_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.folders_id_seq TO team_user;


--
-- TOC entry 5046 (class 0 OID 0)
-- Dependencies: 224
-- Name: TABLE media; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.media TO team_user;


--
-- TOC entry 5048 (class 0 OID 0)
-- Dependencies: 223
-- Name: SEQUENCE media_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.media_id_seq TO team_user;


--
-- TOC entry 5049 (class 0 OID 0)
-- Dependencies: 230
-- Name: TABLE topics_summary; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.topics_summary TO team_user;


--
-- TOC entry 2077 (class 826 OID 42678)
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO team_user;


-- Completed on 2026-06-25 00:30:57

--
-- PostgreSQL database dump complete
--

\unrestrict sByxz3k0aZAHBamajNYPS7xbXWxseRex58M7r6R4d4vDX0042dfz75mnVKnqz1a

