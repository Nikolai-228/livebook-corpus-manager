--
-- PostgreSQL database dump
--

\restrict rWAJ6ntgVw0rTub1iy3GDaMhsFKzsLZZkX1DfpBYVm10avgg7F3tCSQZ7QhaU1q

-- Dumped from database version 18.3
-- Dumped by pg_dump version 18.3

-- Started on 2026-06-17 16:10:51

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
-- TOC entry 232 (class 1259 OID 44962)
-- Name: bigrams; Type: TABLE; Schema: public; Owner: team_user
--

CREATE TABLE public.bigrams (
    id integer NOT NULL,
    id_documents integer NOT NULL,
    bigram text NOT NULL,
    frequency integer DEFAULT 1,
    positions text,
    contexts text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.bigrams OWNER TO team_user;

--
-- TOC entry 231 (class 1259 OID 44961)
-- Name: bigrams_id_seq; Type: SEQUENCE; Schema: public; Owner: team_user
--

CREATE SEQUENCE public.bigrams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.bigrams_id_seq OWNER TO team_user;

--
-- TOC entry 5083 (class 0 OID 0)
-- Dependencies: 231
-- Name: bigrams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: team_user
--

ALTER SEQUENCE public.bigrams_id_seq OWNED BY public.bigrams.id;


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
-- TOC entry 5085 (class 0 OID 0)
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
    type character varying(50)
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
-- TOC entry 5088 (class 0 OID 0)
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
-- TOC entry 5090 (class 0 OID 0)
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
-- TOC entry 5092 (class 0 OID 0)
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
-- TOC entry 5095 (class 0 OID 0)
-- Dependencies: 223
-- Name: media_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.media_id_seq OWNED BY public.media.id;


--
-- TOC entry 236 (class 1259 OID 45008)
-- Name: rake_keywords; Type: TABLE; Schema: public; Owner: team_user
--

CREATE TABLE public.rake_keywords (
    id integer NOT NULL,
    id_documents integer NOT NULL,
    keyword text NOT NULL,
    score double precision DEFAULT 0,
    contexts text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.rake_keywords OWNER TO team_user;

--
-- TOC entry 235 (class 1259 OID 45007)
-- Name: rake_keywords_id_seq; Type: SEQUENCE; Schema: public; Owner: team_user
--

CREATE SEQUENCE public.rake_keywords_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.rake_keywords_id_seq OWNER TO team_user;

--
-- TOC entry 5097 (class 0 OID 0)
-- Dependencies: 235
-- Name: rake_keywords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: team_user
--

ALTER SEQUENCE public.rake_keywords_id_seq OWNED BY public.rake_keywords.id;


--
-- TOC entry 234 (class 1259 OID 44985)
-- Name: trigrams; Type: TABLE; Schema: public; Owner: team_user
--

CREATE TABLE public.trigrams (
    id integer NOT NULL,
    id_documents integer NOT NULL,
    trigram text NOT NULL,
    frequency integer DEFAULT 1,
    positions text,
    contexts text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.trigrams OWNER TO team_user;

--
-- TOC entry 233 (class 1259 OID 44984)
-- Name: trigrams_id_seq; Type: SEQUENCE; Schema: public; Owner: team_user
--

CREATE SEQUENCE public.trigrams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.trigrams_id_seq OWNER TO team_user;

--
-- TOC entry 5098 (class 0 OID 0)
-- Dependencies: 233
-- Name: trigrams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: team_user
--

ALTER SEQUENCE public.trigrams_id_seq OWNED BY public.trigrams.id;


--
-- TOC entry 230 (class 1259 OID 44937)
-- Name: unigrams; Type: TABLE; Schema: public; Owner: team_user
--

CREATE TABLE public.unigrams (
    id integer NOT NULL,
    id_documents integer NOT NULL,
    unigram text NOT NULL,
    frequency integer DEFAULT 1,
    tf_idf_score double precision DEFAULT 0,
    positions text,
    contexts text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.unigrams OWNER TO team_user;

--
-- TOC entry 229 (class 1259 OID 44936)
-- Name: unigrams_id_seq; Type: SEQUENCE; Schema: public; Owner: team_user
--

CREATE SEQUENCE public.unigrams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.unigrams_id_seq OWNER TO team_user;

--
-- TOC entry 5099 (class 0 OID 0)
-- Dependencies: 229
-- Name: unigrams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: team_user
--

ALTER SEQUENCE public.unigrams_id_seq OWNED BY public.unigrams.id;


--
-- TOC entry 4863 (class 2604 OID 44965)
-- Name: bigrams id; Type: DEFAULT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.bigrams ALTER COLUMN id SET DEFAULT nextval('public.bigrams_id_seq'::regclass);


--
-- TOC entry 4850 (class 2604 OID 17059)
-- Name: chapters id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chapters ALTER COLUMN id SET DEFAULT nextval('public.chapters_id_seq'::regclass);


--
-- TOC entry 4851 (class 2604 OID 17084)
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- TOC entry 4855 (class 2604 OID 44474)
-- Name: documents_lemmatized id; Type: DEFAULT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.documents_lemmatized ALTER COLUMN id SET DEFAULT nextval('public.documents_lemmatized_id_seq'::regclass);


--
-- TOC entry 4853 (class 2604 OID 33919)
-- Name: folders id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.folders ALTER COLUMN id SET DEFAULT nextval('public.folders_id_seq'::regclass);


--
-- TOC entry 4852 (class 2604 OID 17106)
-- Name: media id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media ALTER COLUMN id SET DEFAULT nextval('public.media_id_seq'::regclass);


--
-- TOC entry 4869 (class 2604 OID 45011)
-- Name: rake_keywords id; Type: DEFAULT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.rake_keywords ALTER COLUMN id SET DEFAULT nextval('public.rake_keywords_id_seq'::regclass);


--
-- TOC entry 4866 (class 2604 OID 44988)
-- Name: trigrams id; Type: DEFAULT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.trigrams ALTER COLUMN id SET DEFAULT nextval('public.trigrams_id_seq'::regclass);


--
-- TOC entry 4859 (class 2604 OID 44940)
-- Name: unigrams id; Type: DEFAULT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.unigrams ALTER COLUMN id SET DEFAULT nextval('public.unigrams_id_seq'::regclass);


--
-- TOC entry 4904 (class 2606 OID 44974)
-- Name: bigrams bigrams_pkey; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.bigrams
    ADD CONSTRAINT bigrams_pkey PRIMARY KEY (id);


--
-- TOC entry 4873 (class 2606 OID 17063)
-- Name: chapters chapters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.chapters
    ADD CONSTRAINT chapters_pkey PRIMARY KEY (id);


--
-- TOC entry 4888 (class 2606 OID 44483)
-- Name: documents_lemmatized documents_lemmatized_pkey; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.documents_lemmatized
    ADD CONSTRAINT documents_lemmatized_pkey PRIMARY KEY (id);


--
-- TOC entry 4875 (class 2606 OID 17091)
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- TOC entry 4884 (class 2606 OID 33926)
-- Name: folders folders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT folders_pkey PRIMARY KEY (id);


--
-- TOC entry 4882 (class 2606 OID 17112)
-- Name: media media_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_pkey PRIMARY KEY (id);


--
-- TOC entry 4919 (class 2606 OID 45020)
-- Name: rake_keywords rake_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.rake_keywords
    ADD CONSTRAINT rake_keywords_pkey PRIMARY KEY (id);


--
-- TOC entry 4912 (class 2606 OID 44997)
-- Name: trigrams trigrams_pkey; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.trigrams
    ADD CONSTRAINT trigrams_pkey PRIMARY KEY (id);


--
-- TOC entry 4900 (class 2606 OID 44950)
-- Name: unigrams unigrams_pkey; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.unigrams
    ADD CONSTRAINT unigrams_pkey PRIMARY KEY (id);


--
-- TOC entry 4908 (class 2606 OID 44976)
-- Name: bigrams unique_bigram_doc; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.bigrams
    ADD CONSTRAINT unique_bigram_doc UNIQUE (id_documents, bigram);


--
-- TOC entry 4895 (class 2606 OID 44777)
-- Name: documents_lemmatized unique_doc_id; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.documents_lemmatized
    ADD CONSTRAINT unique_doc_id UNIQUE (id_documents);


--
-- TOC entry 4914 (class 2606 OID 44999)
-- Name: trigrams unique_trigram_doc; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.trigrams
    ADD CONSTRAINT unique_trigram_doc UNIQUE (id_documents, trigram);


--
-- TOC entry 4902 (class 2606 OID 44952)
-- Name: unigrams unique_unigram_doc; Type: CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.unigrams
    ADD CONSTRAINT unique_unigram_doc UNIQUE (id_documents, unigram);


--
-- TOC entry 4905 (class 1259 OID 44982)
-- Name: idx_bigrams_doc; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_bigrams_doc ON public.bigrams USING btree (id_documents);


--
-- TOC entry 4906 (class 1259 OID 44983)
-- Name: idx_bigrams_text; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_bigrams_text ON public.bigrams USING btree (bigram);


--
-- TOC entry 4876 (class 1259 OID 46014)
-- Name: idx_documents_chapter_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_chapter_id ON public.documents USING btree (chapter_id);


--
-- TOC entry 4877 (class 1259 OID 46013)
-- Name: idx_documents_content_gin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_content_gin ON public.documents USING gin (to_tsvector('russian'::regconfig, COALESCE(content, ''::text)));


--
-- TOC entry 4878 (class 1259 OID 46015)
-- Name: idx_documents_folder_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_folder_id ON public.documents USING btree (folder_id);


--
-- TOC entry 4879 (class 1259 OID 46016)
-- Name: idx_documents_title; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_title ON public.documents USING btree (title varchar_pattern_ops);


--
-- TOC entry 4880 (class 1259 OID 46017)
-- Name: idx_documents_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_type ON public.documents USING btree (type);


--
-- TOC entry 4885 (class 1259 OID 33938)
-- Name: idx_folders_chapter; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_folders_chapter ON public.folders USING btree (chapter_id);


--
-- TOC entry 4886 (class 1259 OID 33937)
-- Name: idx_folders_parent; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_folders_parent ON public.folders USING btree (parent_folder_id);


--
-- TOC entry 4889 (class 1259 OID 46018)
-- Name: idx_lemmatized_content_gin; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_content_gin ON public.documents_lemmatized USING gin (to_tsvector('russian'::regconfig, COALESCE(content, ''::text)));


--
-- TOC entry 4890 (class 1259 OID 44489)
-- Name: idx_lemmatized_doc_id; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_doc_id ON public.documents_lemmatized USING btree (id_documents);


--
-- TOC entry 4891 (class 1259 OID 46021)
-- Name: idx_lemmatized_stats; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_stats ON public.documents_lemmatized USING btree (unique_lemmas_count, total_tokens_count);


--
-- TOC entry 4892 (class 1259 OID 46020)
-- Name: idx_lemmatized_total_tokens; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_total_tokens ON public.documents_lemmatized USING btree (total_tokens_count);


--
-- TOC entry 4893 (class 1259 OID 46019)
-- Name: idx_lemmatized_unique_lemmas; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_lemmatized_unique_lemmas ON public.documents_lemmatized USING btree (unique_lemmas_count);


--
-- TOC entry 4915 (class 1259 OID 45026)
-- Name: idx_rake_doc; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_rake_doc ON public.rake_keywords USING btree (id_documents);


--
-- TOC entry 4916 (class 1259 OID 45028)
-- Name: idx_rake_keyword; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_rake_keyword ON public.rake_keywords USING btree (keyword);


--
-- TOC entry 4917 (class 1259 OID 45027)
-- Name: idx_rake_score; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_rake_score ON public.rake_keywords USING btree (score DESC);


--
-- TOC entry 4909 (class 1259 OID 45005)
-- Name: idx_trigrams_doc; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_trigrams_doc ON public.trigrams USING btree (id_documents);


--
-- TOC entry 4910 (class 1259 OID 45006)
-- Name: idx_trigrams_text; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_trigrams_text ON public.trigrams USING btree (trigram);


--
-- TOC entry 4896 (class 1259 OID 44958)
-- Name: idx_unigrams_doc; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_unigrams_doc ON public.unigrams USING btree (id_documents);


--
-- TOC entry 4897 (class 1259 OID 44960)
-- Name: idx_unigrams_score; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_unigrams_score ON public.unigrams USING btree (tf_idf_score DESC);


--
-- TOC entry 4898 (class 1259 OID 44959)
-- Name: idx_unigrams_text; Type: INDEX; Schema: public; Owner: team_user
--

CREATE INDEX idx_unigrams_text ON public.unigrams USING btree (unigram);


--
-- TOC entry 4927 (class 2606 OID 44977)
-- Name: bigrams bigrams_id_documents_fkey; Type: FK CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.bigrams
    ADD CONSTRAINT bigrams_id_documents_fkey FOREIGN KEY (id_documents) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- TOC entry 4920 (class 2606 OID 17092)
-- Name: documents documents_chapter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_chapter_id_fkey FOREIGN KEY (chapter_id) REFERENCES public.chapters(id);


--
-- TOC entry 4925 (class 2606 OID 44484)
-- Name: documents_lemmatized documents_lemmatized_id_documents_fkey; Type: FK CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.documents_lemmatized
    ADD CONSTRAINT documents_lemmatized_id_documents_fkey FOREIGN KEY (id_documents) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- TOC entry 4923 (class 2606 OID 33932)
-- Name: folders folders_chapter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT folders_chapter_id_fkey FOREIGN KEY (chapter_id) REFERENCES public.chapters(id);


--
-- TOC entry 4924 (class 2606 OID 33927)
-- Name: folders folders_parent_folder_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.folders
    ADD CONSTRAINT folders_parent_folder_id_fkey FOREIGN KEY (parent_folder_id) REFERENCES public.folders(id) ON DELETE CASCADE;


--
-- TOC entry 4921 (class 2606 OID 17113)
-- Name: media media_chapter_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_chapter_id_fkey FOREIGN KEY (chapter_id) REFERENCES public.chapters(id);


--
-- TOC entry 4922 (class 2606 OID 17123)
-- Name: media media_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- TOC entry 4929 (class 2606 OID 45021)
-- Name: rake_keywords rake_keywords_id_documents_fkey; Type: FK CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.rake_keywords
    ADD CONSTRAINT rake_keywords_id_documents_fkey FOREIGN KEY (id_documents) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- TOC entry 4928 (class 2606 OID 45000)
-- Name: trigrams trigrams_id_documents_fkey; Type: FK CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.trigrams
    ADD CONSTRAINT trigrams_id_documents_fkey FOREIGN KEY (id_documents) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- TOC entry 4926 (class 2606 OID 44953)
-- Name: unigrams unigrams_id_documents_fkey; Type: FK CONSTRAINT; Schema: public; Owner: team_user
--

ALTER TABLE ONLY public.unigrams
    ADD CONSTRAINT unigrams_id_documents_fkey FOREIGN KEY (id_documents) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- TOC entry 5082 (class 0 OID 0)
-- Dependencies: 5
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT ALL ON SCHEMA public TO team_user;


--
-- TOC entry 5084 (class 0 OID 0)
-- Dependencies: 220
-- Name: TABLE chapters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.chapters TO team_user;


--
-- TOC entry 5086 (class 0 OID 0)
-- Dependencies: 219
-- Name: SEQUENCE chapters_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.chapters_id_seq TO team_user;


--
-- TOC entry 5087 (class 0 OID 0)
-- Dependencies: 222
-- Name: TABLE documents; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.documents TO team_user;


--
-- TOC entry 5089 (class 0 OID 0)
-- Dependencies: 221
-- Name: SEQUENCE documents_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.documents_id_seq TO team_user;


--
-- TOC entry 5091 (class 0 OID 0)
-- Dependencies: 226
-- Name: TABLE folders; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.folders TO team_user;


--
-- TOC entry 5093 (class 0 OID 0)
-- Dependencies: 225
-- Name: SEQUENCE folders_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.folders_id_seq TO team_user;


--
-- TOC entry 5094 (class 0 OID 0)
-- Dependencies: 224
-- Name: TABLE media; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.media TO team_user;


--
-- TOC entry 5096 (class 0 OID 0)
-- Dependencies: 223
-- Name: SEQUENCE media_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.media_id_seq TO team_user;


--
-- TOC entry 2092 (class 826 OID 42678)
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO team_user;


-- Completed on 2026-06-17 16:10:51

--
-- PostgreSQL database dump complete
--

\unrestrict rWAJ6ntgVw0rTub1iy3GDaMhsFKzsLZZkX1DfpBYVm10avgg7F3tCSQZ7QhaU1q

