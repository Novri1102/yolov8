// ==== Hapus riwayat ====
document.querySelectorAll(".btn-hapus").forEach(btn => {
    btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm("Hapus riwayat ini?")) return;
        try {
            const res = await fetch(`/riwayat/hapus/${id}`, { method: "POST" });
            if (res.ok) {
                document.getElementById(`row-${id}`).remove();
                showToast("Riwayat berhasil dihapus.", "success");
            } else {
                showToast("Gagal menghapus riwayat.", "error");
            }
        } catch (err) {
            showToast("Gagal terhubung ke server.", "error");
        }
    });
});

// ==== Modal detail ====
const detailModal = document.getElementById("detailModal");
const btnCloseModal = document.getElementById("btnCloseModal");
const modalTitle = document.getElementById("modalTitle");
const modalImg = document.getElementById("modalImg");
const modalMeta = document.getElementById("modalMeta");
const modalDetailList = document.getElementById("modalDetailList");

document.querySelectorAll(".btn-detail").forEach(btn => {
    btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        try {
            const res = await fetch(`/api/riwayat/${id}`);
            const data = await res.json();
            if (!res.ok) {
                showToast(data.error || "Gagal memuat detail.", "error");
                return;
            }

            modalTitle.textContent = `Detail Deteksi #${data.id}`;
            modalImg.src = `/static/annotated/${data.nama_file_hasil}`;
            modalMeta.innerHTML = `
                <div><b>Waktu:</b> ${data.waktu}</div>
                <div><b>Operator:</b> ${data.operator || "-"}</div>
                <div><b>Catatan:</b> ${data.catatan || "-"}</div>
                <div><b>File Asli:</b> ${data.nama_file_asli}</div>
                <div><b>Total:</b> ${data.total_kecambah} &nbsp;
                     <span class="text-layak">Layak: ${data.total_layak}</span> &nbsp;
                     <span class="text-tidak-layak">Tidak Layak: ${data.total_tidak_layak}</span> &nbsp;
                     (${data.persentase_layak}%)</div>
            `;

            modalDetailList.innerHTML = "";
            if (!data.detections || data.detections.length === 0) {
                modalDetailList.innerHTML = `<p class="empty-msg">Tidak ada rincian tersimpan untuk sesi ini.</p>`;
            } else {
                data.detections.forEach((det, idx) => {
                    const isLayak = det.class_id === 0;
                    const row = document.createElement("div");
                    row.className = `detail-item ${isLayak ? "layak" : "tidak-layak"}`;
                    row.innerHTML = `
                        <span class="detail-idx">#${idx + 1}</span>
                        <span class="detail-label">${det.label}</span>
                        <span class="detail-conf">${(det.confidence * 100).toFixed(1)}%</span>
                    `;
                    modalDetailList.appendChild(row);
                });
            }

            detailModal.classList.add("show");
        } catch (err) {
            showToast("Gagal terhubung ke server.", "error");
        }
    });
});

btnCloseModal.addEventListener("click", () => detailModal.classList.remove("show"));
detailModal.addEventListener("click", (e) => {
    if (e.target === detailModal) detailModal.classList.remove("show");
});

// ==== Filter tabel ====
const filterKeyword = document.getElementById("filterKeyword");
const filterFrom = document.getElementById("filterFrom");
const filterTo = document.getElementById("filterTo");
const btnResetFilter = document.getElementById("btnResetFilter");
const historyTable = document.getElementById("historyTable");
const noResultMsg = document.getElementById("noResultMsg");

function applyFilter() {
    if (!historyTable) return;
    const keyword = filterKeyword.value.trim().toLowerCase();
    const fromDate = filterFrom.value;
    const toDate = filterTo.value;
    let visibleCount = 0;

    historyTable.querySelectorAll("tbody tr").forEach(row => {
        const rowKeyword = row.dataset.keyword || "";
        const rowDate = row.dataset.date || "";

        let match = true;
        if (keyword && !rowKeyword.includes(keyword)) match = false;
        if (fromDate && rowDate < fromDate) match = false;
        if (toDate && rowDate > toDate) match = false;

        row.style.display = match ? "" : "none";
        if (match) visibleCount++;
    });

    noResultMsg.style.display = visibleCount === 0 ? "block" : "none";
}

if (filterKeyword) {
    filterKeyword.addEventListener("input", applyFilter);
    filterFrom.addEventListener("change", applyFilter);
    filterTo.addEventListener("change", applyFilter);
    btnResetFilter.addEventListener("click", () => {
        filterKeyword.value = "";
        filterFrom.value = "";
        filterTo.value = "";
        applyFilter();
    });
}

// ==== Grafik statistik ====
async function renderCharts() {
    try {
        const res = await fetch("/api/statistik");
        const data = await res.json();

        // Pie chart: layak vs tidak layak
        new Chart(document.getElementById("chartPie"), {
            type: "doughnut",
            data: {
                labels: ["Layak Salur", "Tidak Layak Salur"],
                datasets: [{
                    data: [data.ringkasan.total_layak, data.ringkasan.total_tidak_layak],
                    backgroundColor: ["#40916c", "#d64545"],
                    borderWidth: 0,
                }],
            },
            options: {
                plugins: { legend: { position: "bottom" } },
                maintainAspectRatio: true,
            },
        });

        // Bar chart: tren harian
        const labels = data.harian.map(d => d.tanggal);
        new Chart(document.getElementById("chartTren"), {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Layak Salur",
                        data: data.harian.map(d => d.layak),
                        backgroundColor: "#40916c",
                    },
                    {
                        label: "Tidak Layak Salur",
                        data: data.harian.map(d => d.tidak_layak),
                        backgroundColor: "#d64545",
                    },
                ],
            },
            options: {
                plugins: { legend: { position: "bottom" } },
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
                },
                maintainAspectRatio: true,
            },
        });
    } catch (err) {
        console.error("Gagal memuat grafik statistik:", err);
    }
}

renderCharts();
