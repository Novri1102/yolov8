// ==== Elemen ====
const tabBtns = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const previewWrap = document.getElementById("previewWrap");
const previewImg = document.getElementById("previewImg");
const btnClearPreview = document.getElementById("btnClearPreview");

const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const btnStartCam = document.getElementById("btnStartCam");
const btnCapture = document.getElementById("btnCapture");

const inputOperator = document.getElementById("inputOperator");
const inputCatatan = document.getElementById("inputCatatan");

const confSlider = document.getElementById("confSlider");
const confVal = document.getElementById("confVal");
const iouSlider = document.getElementById("iouSlider");
const iouVal = document.getElementById("iouVal");

const btnDeteksi = document.getElementById("btnDeteksi");
const loadingIndicator = document.getElementById("loadingIndicator");

const resultSection = document.getElementById("resultSection");
const resultImg = document.getElementById("resultImg");
const resTotal = document.getElementById("resTotal");
const resLayak = document.getElementById("resLayak");
const resTidakLayak = document.getElementById("resTidakLayak");
const resPersen = document.getElementById("resPersen");
const btnDownload = document.getElementById("btnDownload");
const detailList = document.getElementById("detailList");

let currentFile = null;       // File dari upload
let currentBase64 = null;     // base64 dari kamera
let cameraStream = null;

// ==== Tab switching ====
tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        tabBtns.forEach(b => b.classList.remove("active"));
        tabContents.forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
        resetSelection();
    });
});

function resetSelection() {
    currentFile = null;
    currentBase64 = null;
    btnDeteksi.disabled = true;
    previewWrap.style.display = "none";
    dropzone.style.display = "block";
    fileInput.value = "";
}

// ==== Upload gambar ====
dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length > 0) {
        handleFileSelected(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
        handleFileSelected(fileInput.files[0]);
    }
});

function handleFileSelected(file) {
    if (!file.type.startsWith("image/")) {
        showToast("File harus berupa gambar.", "error");
        return;
    }
    currentFile = file;
    currentBase64 = null;
    const reader = new FileReader();
    reader.onload = (e) => {
        previewImg.src = e.target.result;
        previewWrap.style.display = "block";
        dropzone.style.display = "none";
        btnDeteksi.disabled = false;
    };
    reader.readAsDataURL(file);
}

btnClearPreview.addEventListener("click", resetSelection);

// ==== Kamera ====
btnStartCam.addEventListener("click", async () => {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        video.srcObject = cameraStream;
        btnCapture.disabled = false;
        btnStartCam.textContent = "Kamera Aktif";
        btnStartCam.disabled = true;
    } catch (err) {
        showToast("Tidak dapat mengakses kamera: " + err.message, "error");
    }
});

btnCapture.addEventListener("click", () => {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    currentBase64 = canvas.toDataURL("image/jpeg", 0.92);
    currentFile = null;
    btnDeteksi.disabled = false;
    showToast("Foto berhasil diambil. Klik 'Jalankan Deteksi'.", "success");
});

// ==== Threshold sliders ====
confSlider.addEventListener("input", () => confVal.textContent = confSlider.value);
iouSlider.addEventListener("input", () => iouVal.textContent = iouSlider.value);

// ==== Render detail per-kecambah ====
function renderDetailList(detections) {
    detailList.innerHTML = "";
    if (!detections || detections.length === 0) {
        detailList.innerHTML = `<p class="empty-msg">Tidak ada kecambah terdeteksi pada threshold saat ini.</p>`;
        return;
    }
    detections.forEach((det, idx) => {
        const isLayak = det.class_id === 0;
        const row = document.createElement("div");
        row.className = `detail-item ${isLayak ? "layak" : "tidak-layak"}`;
        row.innerHTML = `
            <span class="detail-idx">#${idx + 1}</span>
            <span class="detail-label">${det.label}</span>
            <span class="detail-conf">${(det.confidence * 100).toFixed(1)}%</span>
        `;
        detailList.appendChild(row);
    });
}

// ==== Jalankan deteksi ====
btnDeteksi.addEventListener("click", async () => {
    if (!currentFile && !currentBase64) {
        showToast("Silakan pilih atau ambil gambar terlebih dahulu.", "error");
        return;
    }

    const formData = new FormData();
    if (currentFile) {
        formData.append("gambar", currentFile);
    } else {
        formData.append("gambar_base64", currentBase64);
    }
    formData.append("conf", confSlider.value);
    formData.append("iou", iouSlider.value);
    formData.append("operator", inputOperator.value.trim());
    formData.append("catatan", inputCatatan.value.trim());

    btnDeteksi.disabled = true;
    loadingIndicator.style.display = "block";
    resultSection.style.display = "none";

    try {
        const res = await fetch("/api/deteksi", { method: "POST", body: formData });
        const data = await res.json();

        if (!res.ok) {
            showToast(data.error || "Terjadi kesalahan saat deteksi.", "error");
            return;
        }

        resultImg.src = data.gambar_hasil_url;
        resTotal.textContent = data.total_kecambah;
        resLayak.textContent = data.total_layak;
        resTidakLayak.textContent = data.total_tidak_layak;
        resPersen.textContent = data.persentase_layak + "%";
        btnDownload.href = data.gambar_hasil_url;
        renderDetailList(data.detections);

        resultSection.style.display = "block";
        resultSection.scrollIntoView({ behavior: "smooth" });
        showToast(`Deteksi selesai: ${data.total_kecambah} kecambah ditemukan.`, "success");
    } catch (err) {
        showToast("Gagal terhubung ke server: " + err.message, "error");
    } finally {
        btnDeteksi.disabled = false;
        loadingIndicator.style.display = "none";
    }
});
