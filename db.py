# -*- coding: utf-8 -*-
import sqlite3
import psycopg2
from config import CONFIG
from logger import log

_conn = None
_db_type = None

def init():
    global _conn, _db_type
    cfg = CONFIG["database"]
    _db_type = cfg.get("type", "").lower()

    if _db_type in ("pg", "postgresql"):
        dsn = f"postgresql://{cfg['user']}:{cfg['passwd']}@{cfg['host']}:{cfg['port']}/{cfg['db']}"
        _conn = psycopg2.connect(dsn)
        _conn.autocommit = True
        _ensure_table_pg()
        log.info("[DB]PgSQL is OK!")
    elif _db_type == "sqlite":
        _conn = sqlite3.connect("sql.db", check_same_thread=False)
        _ensure_table_sqlite()
        log.info("[SQLite]READY!")
    else:
        log.error("[DB]无效的数据库类型")
        raise SystemExit(1)

def _ensure_table_pg():
    with _conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS at (
            msg_id BIGINT PRIMARY KEY,
            comment_a_id BIGINT,
            comment_root_id BIGINT,
            link_id BIGINT,
            user_a_id BIGINT,
            comment_text TEXT,
            reply BOOLEAN
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS link_reply (
            link_id BIGINT PRIMARY KEY,
            handled BOOLEAN,
            replied BOOLEAN
        )
        """)

def _ensure_table_sqlite():
    cur = _conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS at (
        msg_id BIGINT PRIMARY KEY,
        comment_a_id BIGINT,
        comment_root_id BIGINT,
        link_id BIGINT,
        user_a_id BIGINT,
        comment_text TEXT,
        reply BOOLEAN
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS link_reply (
        link_id BIGINT PRIMARY KEY,
        handled BOOLEAN,
        replied BOOLEAN
    )
    """)
    _conn.commit()

def insert(msg_id, comment_a_id, comment_root_id, link_id, user_a_id, comment_text, reply):
    if _db_type in ("pg", "postgresql"):
        with _conn.cursor() as cur:
            cur.execute("""
            INSERT INTO at (msg_id,comment_a_id,comment_root_id,link_id,user_a_id,comment_text,reply)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (msg_id) DO NOTHING
            """, (msg_id, comment_a_id, comment_root_id, link_id, user_a_id, comment_text, reply))
        return True
    if _db_type == "sqlite":
        cur = _conn.cursor()
        cur.execute("""
        INSERT INTO at (msg_id,comment_a_id,comment_root_id,link_id,user_a_id,comment_text,reply)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT (msg_id) DO NOTHING
        """, (msg_id, comment_a_id, comment_root_id, link_id, user_a_id, comment_text, reply))
        _conn.commit()
        return True
    return False

def replied(comment_id):
    if _db_type in ("pg", "postgresql"):
        with _conn.cursor() as cur:
            cur.execute("UPDATE at SET reply=%s WHERE comment_a_id=%s", (True, comment_id))
    elif _db_type == "sqlite":
        cur = _conn.cursor()
        cur.execute("UPDATE at SET reply=? WHERE comment_a_id=?", (True, comment_id))
        _conn.commit()

def is_replied(comment_id) -> bool:
    if _db_type in ("pg", "postgresql"):
        with _conn.cursor() as cur:
            cur.execute("SELECT 1 FROM at WHERE comment_a_id=%s AND reply=true LIMIT 1", (comment_id,))
            return cur.fetchone() is not None
    if _db_type == "sqlite":
        cur = _conn.cursor()
        cur.execute("SELECT 1 FROM at WHERE comment_a_id=? AND reply=1 LIMIT 1", (comment_id,))
        return cur.fetchone() is not None
    return False

def get_comm():
    rows = []
    if _db_type in ("pg", "postgresql"):
        with _conn.cursor() as cur:
            cur.execute("SELECT link_id,comment_a_id,comment_root_id,comment_text,user_a_id FROM at WHERE reply=false LIMIT 3")
            rows = cur.fetchall()
    elif _db_type == "sqlite":
        cur = _conn.cursor()
        cur.execute("SELECT link_id,comment_a_id,comment_root_id,comment_text,user_a_id FROM at WHERE reply=false LIMIT 3")
        rows = cur.fetchall()

    return [
        {"link_id": r[0], "comment_id": r[1], "root_id": r[2], "text": r[3], "uid": r[4]}
        for r in rows
    ]

def is_new():
    if _db_type in ("pg", "postgresql"):
        with _conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM at")
            num = cur.fetchone()[0]
    else:
        cur = _conn.cursor()
        cur.execute("SELECT COUNT(*) FROM at")
        num = cur.fetchone()[0]
    return num == 0

def link_handled(link_id: int) -> bool:
    if _db_type in ("pg", "postgresql"):
        with _conn.cursor() as cur:
            cur.execute("SELECT replied FROM link_reply WHERE link_id=%s", (link_id,))
            row = cur.fetchone()
    else:
        cur = _conn.cursor()
        cur.execute("SELECT replied FROM link_reply WHERE link_id=?", (link_id,))
        row = cur.fetchone()
    return bool(row[0]) if row else False

def link_set(link_id: int, replied: bool):
    if _db_type in ("pg", "postgresql"):
        with _conn.cursor() as cur:
            cur.execute("""
            INSERT INTO link_reply (link_id, handled, replied)
            VALUES (%s,%s,%s)
            ON CONFLICT (link_id) DO UPDATE SET handled=EXCLUDED.handled, replied=EXCLUDED.replied
            """, (link_id, True, replied))
    elif _db_type == "sqlite":
        cur = _conn.cursor()
        cur.execute("""
        INSERT INTO link_reply (link_id, handled, replied)
        VALUES (?,?,?)
        ON CONFLICT (link_id) DO UPDATE SET handled=excluded.handled, replied=excluded.replied
        """, (link_id, True, replied))
        _conn.commit()