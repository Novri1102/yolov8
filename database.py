"""
database.py
Mengelola penyimpanan riwayat deteksi kecambah kelapa sawit
menggunakan SQLite (file: kecambah.db, otomatis dibuat saat pertama kali run).
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "kecambah.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Membuat tabel riwayat_deteksi jika belum ada, dan migrasi kolom baru bila perlu."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS riwayat_deteksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waktu TEXT NOT NULL,
            nama_file_asli TEXT,
            nama_file_hasil TEXT,
            total_kecambah INTEGER,
            total_layak INTEGER,
            total_tidak_layak INTEGER,
            persentase_layak REAL,
            operator TEXT,
            catatan TEXT,
            detections_json TEXT
        )
        """
    )
    conn.commit()

    # Migrasi otomatis: kalau database lama sudah ada tapi belum punya kolom baru
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(riwayat_deteksi)")}
    migrations = {
        "operator": "ALTER TABLE riwayat_deteksi ADD COLUMN operator TEXT",
        "catatan": "ALTER TABLE riwayat_deteksi ADD COLUMN catatan TEXT",
        "detections_json": "ALTER TABLE riwayat_deteksi ADD COLUMN detections_json TEXT",
    }
    for col, ddl in migrations.items():
        if col not in existing_cols:
            conn.execute(ddl)
    conn.commit()
    conn.close()


def simpan_hasil(nama_file_asli, nama_file_hasil, total_layak, total_tidak_layak,
                  operator=None, catatan=None, detections=None):
    """Menyimpan satu baris hasil deteksi ke database, mengembalikan id record baru."""
    total = total_layak + total_tidak_layak
    persentase = round((total_layak / total) * 100, 2) if total > 0 else 0.0
    detections_json = json.dumps(detections or [], ensure_ascii=False)

    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO riwayat_deteksi
            (waktu, nama_file_asli, nama_file_hasil, total_kecambah,
             total_layak, total_tidak_layak, persentase_layak,
             operator, catatan, detections_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            nama_file_asli,
            nama_file_hasil,
            total,
            total_layak,
            total_tidak_layak,
            persentase,
            operator,
            catatan,
            detections_json,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def ambil_semua_riwayat():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM riwayat_deteksi ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return rows


def ambil_riwayat_by_id(item_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM riwayat_deteksi WHERE id = ?", (item_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def ambil_ringkasan():
    """Statistik total untuk dashboard."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_sesi,
            COALESCE(SUM(total_kecambah), 0) AS total_kecambah,
            COALESCE(SUM(total_layak), 0) AS total_layak,
            COALESCE(SUM(total_tidak_layak), 0) AS total_tidak_layak
        FROM riwayat_deteksi
        """
    ).fetchone()
    conn.close()
    return dict(row)


def ambil_statistik_harian(limit_hari=14):
    """Total layak/tidak layak per tanggal (untuk grafik tren), dari hari terbaru."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            substr(waktu, 1, 10) AS tanggal,
            SUM(total_layak) AS layak,
            SUM(total_tidak_layak) AS tidak_layak
        FROM riwayat_deteksi
        GROUP BY tanggal
        ORDER BY tanggal DESC
        LIMIT ?
        """,
        (limit_hari,),
    ).fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    data.reverse()  # urut dari tanggal terlama -> terbaru untuk grafik
    return data


def hapus_riwayat(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM riwayat_deteksi WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
