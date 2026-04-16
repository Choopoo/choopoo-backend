CREATE TABLE IF NOT EXISTS pages (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    title TEXT,
    meta_description TEXT,
    score FLOAT,
    crawled_at TIMESTAMP DEFAULT NOW(),
    material TEXT,
    source_label TEXT,
    job_id TEXT
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id SERIAL PRIMARY KEY,
    page_id INTEGER REFERENCES pages(id),
    summary TEXT,
    recommendation TEXT,
    processed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_pages_domain ON pages(domain);
CREATE INDEX idx_pages_crawled_at ON pages(crawled_at);
