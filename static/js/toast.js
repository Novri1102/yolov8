/**
 * toast.js — notifikasi kecil pengganti alert() bawaan browser.
 * Pemakaian: showToast("Pesan", "success" | "error" | "info")
 */
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const icons = { success: "✅", error: "⚠️", info: "ℹ️" };
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span>${message}</span>`;

    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));

    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 300);
    }, 3800);
}
