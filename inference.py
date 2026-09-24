"""
inference.py
Wrapper untuk model YOLOv8 (best.tflite) yang mendeteksi kecambah kelapa sawit
dengan 2 kelas: LAYAK SALUR dan TIDAK LAYAK SALUR.

Model info (dibaca dari metadata best.tflite):
- Input  : 1x3x640x640 float32, RGB, dinormalisasi 0-1 (channel-first / NCHW)
- Output : 1x6x8400  -> 4 (cx,cy,w,h dalam skala 0-1 relatif ke 640) + 2 skor kelas
- Kelas  : 0 = LAYAK SALUR, 1 = TIDAK LAYAK SALUR
"""

import numpy as np
import cv2
from pathlib import Path

MODEL_PATH = Path(__file__).parent / "best.tflite"
INPUT_SIZE = 640

CLASS_NAMES = {0: "LAYAK SALUR", 1: "TIDAK LAYAK SALUR"}
CLASS_COLORS = {
    0: (46, 184, 92),    # hijau  -> layak salur
    1: (66, 66, 235),    # merah  -> tidak layak salur (BGR untuk cv2)
}

# --- Load interpreter TFLite (coba beberapa backend agar fleksibel) ---
_Interpreter = None
try:
    from ai_edge_litert.interpreter import Interpreter as _Interpreter
except ImportError:
    try:
        import tflite_runtime.interpreter as _tflite
        _Interpreter = _tflite.Interpreter
    except ImportError:
        import tensorflow as tf
        _Interpreter = tf.lite.Interpreter


class KecambahDetector:
    def __init__(self, model_path=MODEL_PATH, conf_threshold=0.35, iou_threshold=0.45):
        self.interpreter = _Interpreter(model_path=str(model_path))
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

    # ---------- Preprocessing ----------
    @staticmethod
    def _letterbox(image, new_size=INPUT_SIZE, color=(114, 114, 114)):
        """Resize gambar menjaga aspect ratio, sisanya diberi padding abu-abu."""
        h, w = image.shape[:2]
        r = min(new_size / h, new_size / w)
        new_unpad_w, new_unpad_h = int(round(w * r)), int(round(h * r))

        resized = cv2.resize(image, (new_unpad_w, new_unpad_h), interpolation=cv2.INTER_LINEAR)

        dw, dh = new_size - new_unpad_w, new_size - new_unpad_h
        top, bottom = dh // 2, dh - dh // 2
        left, right = dw // 2, dw - dw // 2

        padded = cv2.copyMakeBorder(resized, top, bottom, left, right,
                                     cv2.BORDER_CONSTANT, value=color)
        return padded, r, left, top

    def _preprocess(self, image_bgr):
        padded, r, pad_left, pad_top = self._letterbox(image_bgr, INPUT_SIZE)
        img_rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        img_norm = img_rgb.astype(np.float32) / 255.0
        img_chw = np.transpose(img_norm, (2, 0, 1))          # HWC -> CHW
        img_batch = np.expand_dims(img_chw, axis=0)          # -> 1x3x640x640
        return img_batch, r, pad_left, pad_top

    # ---------- Postprocessing ----------
    def _postprocess(self, raw_output, r, pad_left, pad_top, orig_w, orig_h):
        preds = raw_output[0].T  # (8400, 6)

        boxes_cxcywh = preds[:, :4] * INPUT_SIZE
        scores_all = preds[:, 4:]
        class_ids = np.argmax(scores_all, axis=1)
        confidences = np.max(scores_all, axis=1)

        keep = confidences >= self.conf_threshold
        boxes_cxcywh = boxes_cxcywh[keep]
        class_ids = class_ids[keep]
        confidences = confidences[keep]

        if len(boxes_cxcywh) == 0:
            return []

        # cx,cy,w,h (skala 640 dg padding) -> x1,y1,x2,y2 (skala gambar asli)
        cx, cy, w, h = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
        x1 = (cx - w / 2 - pad_left) / r
        y1 = (cy - h / 2 - pad_top) / r
        x2 = (cx + w / 2 - pad_left) / r
        y2 = (cy + h / 2 - pad_top) / r

        x1 = np.clip(x1, 0, orig_w - 1)
        y1 = np.clip(y1, 0, orig_h - 1)
        x2 = np.clip(x2, 0, orig_w - 1)
        y2 = np.clip(y2, 0, orig_h - 1)

        boxes_xywh_for_nms = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
        confidences_list = confidences.tolist()

        indices = cv2.dnn.NMSBoxes(
            boxes_xywh_for_nms, confidences_list,
            score_threshold=self.conf_threshold,
            nms_threshold=self.iou_threshold,
        )

        results = []
        if len(indices) > 0:
            indices = np.array(indices).flatten()
            for i in indices:
                results.append({
                    "class_id": int(class_ids[i]),
                    "label": CLASS_NAMES[int(class_ids[i])],
                    "confidence": round(float(confidences[i]), 4),
                    "box": [float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i])],
                })
        return results

    # ---------- API utama ----------
    def detect(self, image_bgr):
        """Menjalankan deteksi pada satu gambar (numpy array BGR / hasil cv2.imread)."""
        orig_h, orig_w = image_bgr.shape[:2]
        input_tensor, r, pad_left, pad_top = self._preprocess(image_bgr)

        self.interpreter.set_tensor(self.input_details[0]["index"], input_tensor)
        self.interpreter.invoke()
        raw_output = self.interpreter.get_tensor(self.output_details[0]["index"])

        detections = self._postprocess(raw_output, r, pad_left, pad_top, orig_w, orig_h)
        return detections

    @staticmethod
    def gambar_hasil(image_bgr, detections):
        """Menggambar bounding box + label pada gambar, mengembalikan gambar baru (BGR)."""
        out_img = image_bgr.copy()
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["box"]]
            color = CLASS_COLORS[det["class_id"]]
            thickness = max(2, int(round((out_img.shape[0] + out_img.shape[1]) / 700)))

            cv2.rectangle(out_img, (x1, y1), (x2, y2), color, thickness)

            label_text = f"{det['label']} {det['confidence']*100:.1f}%"
            font_scale = max(0.5, thickness / 3.5)
            (tw, th), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 2)

            label_y1 = max(y1 - th - baseline - 4, 0)
            cv2.rectangle(out_img, (x1, label_y1), (x1 + tw + 6, label_y1 + th + baseline + 4), color, -1)
            cv2.putText(out_img, label_text, (x1 + 3, label_y1 + th + 2),
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 2, cv2.LINE_AA)
        return out_img

    @staticmethod
    def hitung_ringkasan(detections):
        layak = sum(1 for d in detections if d["class_id"] == 0)
        tidak_layak = sum(1 for d in detections if d["class_id"] == 1)
        return layak, tidak_layak
