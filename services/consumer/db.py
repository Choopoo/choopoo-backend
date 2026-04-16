import psycopg2
from psycopg2 import pool


class Database:
    def __init__(self, host, port, user, password, dbname):
        self.pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=host,
            port=int(port),
            user=user,
            password=password,
            dbname=dbname,
        )
        self._create_table()

    def _create_table(self):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pages (
                        id SERIAL PRIMARY KEY,
                        url TEXT UNIQUE NOT NULL,
                        domain TEXT,
                        title TEXT,
                        meta_description TEXT,
                        score REAL,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                for stmt in (
                    "ALTER TABLE pages ADD COLUMN IF NOT EXISTS crawled_at TIMESTAMP DEFAULT NOW()",
                    "ALTER TABLE pages ADD COLUMN IF NOT EXISTS material TEXT",
                    "ALTER TABLE pages ADD COLUMN IF NOT EXISTS source_label TEXT",
                    "ALTER TABLE pages ADD COLUMN IF NOT EXISTS job_id TEXT",
                ):
                    cur.execute(stmt)
            conn.commit()
        finally:
            self.pool.putconn(conn)

    def insert_page(
        self,
        url,
        domain,
        title,
        meta_description,
        score,
        material=None,
        source_label=None,
        job_id=None,
    ):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pages (url, domain, title, meta_description, score, material, source_label, job_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO UPDATE SET
                        score = EXCLUDED.score,
                        title = EXCLUDED.title,
                        meta_description = EXCLUDED.meta_description,
                        material = EXCLUDED.material,
                        source_label = EXCLUDED.source_label,
                        job_id = EXCLUDED.job_id
                    RETURNING id
                    """,
                    (url, domain, title, meta_description, score, material, source_label, job_id),
                )
                page_id = cur.fetchone()[0]
            conn.commit()
            return page_id
        finally:
            self.pool.putconn(conn)

    def get_page_by_url(self, url):
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, url, domain, title, score FROM pages WHERE url = %s", (url,))
                row = cur.fetchone()
                if row:
                    return {"id": row[0], "url": row[1], "domain": row[2], "title": row[3], "score": row[4]}
                return None
        finally:
            self.pool.putconn(conn)

    def close(self):
        self.pool.closeall()
