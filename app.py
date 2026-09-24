"""
app.py
Web app deteksi kecambah kelapa sawit (LAYAK SALUR / TIDAK LAYAK SALUR)
Pusat Penelitian Kelapa Sawit

Cara jalankan:
    python app.py
Lalu buka browser ke: http://127.0.0.1:5000
"""

import base64
import uuid
import io
import csv
import json
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify, send_from_directory, Response

from inference import KecambahDetector
import database

BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
ANNOTATED_DIR = BASE_DIR / "static" / "annotated"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ANNOTATED_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {"png", "jpg", "jpeg", "webp", "bmp"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # maks 16 MB per upload

database.init_db()
detector = KecambahDetector()  # model dimuat sekali saat server start


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


@app.route("/")
def index():
    ringkasan = database.ambil_ringkasan()
    return render_template("index.html", ringkasan=ringkasan)


@app.route("/riwayat")
def riwayat():
    data = database.ambil_semua_riwayat()
    ringkasan = database.ambil_ringkasan()
    return render_template("history.html", riwayat=data, ringkasan=ringkasan)


@app.route("/riwayat/hapus/<int:item_id>", methods=["POST"])
def hapus_riwayat(item_id):
    database.hapus_riwayat(item_id)
    return jsonify({"status": "ok"})


@app.route("/api/riwayat/<int:item_id>")
def api_riwayat_detail(item_id):
    """Detail satu sesi deteksi, termasuk daftar tiap kecambah yang terdeteksi."""
    row = database.ambil_riwayat_by_id(item_id)
    if row is None:
        return jsonify({"error": "Data tidak ditemukan."}), 404
    row["detections"] = json.loads(row.get("detections_json") or "[]")
    return jsonify(row)


@app.route("/api/statistik")
def api_statistik():
    """Data untuk grafik: ringkasan total + tren harian."""
    ringkasan = database.ambil_ringkasan()
    harian = database.ambil_statistik_harian(limit_hari=14)
    return jsonify({"ringkasan": ringkasan, "harian": harian})


@app.route("/riwayat/ekspor")
def ekspor_csv():
    """Unduh seluruh riwayat deteksi dalam format CSV (bisa dibuka di Excel)."""
    rows = database.ambil_semua_riwayat()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID", "Waktu", "Operator", "Nama File Asli", "Total Kecambah",
        "Layak Salur", "Tidak Layak Salur", "Persentase Layak (%)", "Catatan",
    ])
    for r in rows:
        writer.writerow([
            r["id"], r["waktu"], r["operator"] or "-", r["nama_file_asli"],
            r["total_kecambah"], r["total_layak"], r["total_tidak_layak"],
            r["persentase_layak"], r["catatan"] or "-",
        ])

    output = buffer.getvalue()
    buffer.close()

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=riwayat_deteksi_kecambah.csv"},
    )


@app.route("/api/deteksi", methods=["POST"])
def api_deteksi():
    """
    Menerima gambar (form-data field 'gambar', bisa dari file upload
    atau dari kamera/base64), menjalankan deteksi, menyimpan hasil
    ke folder + database, mengembalikan JSON.
    """
    file_bytes = None
    original_filename = "capture.jpg"

    if "gambar" in request.files and request.files["gambar"].filename != "":
        f = request.files["gambar"]
        if not allowed_file(f.filename):
            return jsonify({"error": "Format file tidak didukung."}), 400
        original_filename = f.filename
        file_bytes = f.read()
    elif request.form.get("gambar_base64"):
        b64_data = request.form["gambar_base64"].split(",")[-1]
        file_bytes = base64.b64decode(b64_data)
        original_filename = "webcam_capture.jpg"
    else:
        return jsonify({"error": "Tidak ada gambar yang dikirim."}), 400

    npimg = np.frombuffer(file_bytes, np.uint8)
    image_bgr = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    if image_bgr is None:
        return jsonify({"error": "Gagal membaca gambar. Pastikan file gambar valid."}), 400

    conf = float(request.form.get("conf", 0.35))
    iou = float(request.form.get("iou", 0.45))
    operator = request.form.get("operator", "").strip() or None
    catatan = request.form.get("catatan", "").strip() or None
    detector.conf_threshold = max(0.05, min(conf, 0.95))
    detector.iou_threshold = max(0.05, min(iou, 0.95))

    detections = detector.detect(image_bgr)
    annotated = detector.gambar_hasil(image_bgr, detections)
    layak, tidak_layak = detector.hitung_ringkasan(detections)

    uid = uuid.uuid4().hex[:10]
    ext = ".jpg"
    hasil_filename = f"{uid}{ext}"
    hasil_path = ANNOTATED_DIR / hasil_filename
    cv2.imwrite(str(hasil_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])

    record_id = database.simpan_hasil(
        nama_file_asli=original_filename,
        nama_file_hasil=hasil_filename,
        total_layak=layak,
        total_tidak_layak=tidak_layak,
        operator=operator,
        catatan=catatan,
        detections=detections,
    )

    total = layak + tidak_layak
    persentase = round((layak / total) * 100, 2) if total > 0 else 0.0

    return jsonify({
        "status": "ok",
        "id": record_id,
        "gambar_hasil_url": f"/static/annotated/{hasil_filename}",
        "total_kecambah": total,
        "total_layak": layak,
        "total_tidak_layak": tidak_layak,
        "persentase_layak": persentase,
        "detections": detections,
    })


@app.route("/static/annotated/<path:filename>")
def annotated_file(filename):
    return send_from_directory(ANNOTATED_DIR, filename)


if __name__ == "__main__":
    print("=" * 60)
    print(" Web Deteksi Kecambah Kelapa Sawit")
    print(" Pusat Penelitian Kelapa Sawit")
    print(" Buka browser: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)
