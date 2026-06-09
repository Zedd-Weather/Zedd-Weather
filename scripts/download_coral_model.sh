#!/usr/bin/env bash
# =============================================================================
# Zedd Weather – Coral Model Downloader
# =============================================================================
# Downloads a pre-trained TensorFlow Lite model and label file for use with
# the Google Coral Edge TPU on the Raspberry Pi Zero 2WH.
#
# Usage:
#   sudo ./download_coral_model.sh [--models-dir /opt/zedd/models]
#
# The script pulls a lightweight weather-classification model (edgetpu.tflite)
# from a public release bucket and places it at the path expected by the
# Pi Zero collector (CORAL_MODEL_PATH).
#
# If you have your own .tflite model, simply place it at:
#   /opt/zedd/models/weather_classify_edgetpu.tflite
# and skip this script.
# =============================================================================

set -euo pipefail

MODELS_DIR="${1:-/opt/zedd/models}"
MODEL_URL="${MODEL_URL:-https://github.com/WilliamMajanja/Zedd-Weather/releases/download/v0.1/weather_classify_edgetpu.tflite}"
LABELS_URL="${LABELS_URL:-https://github.com/WilliamMajanja/Zedd-Weather/releases/download/v0.1/weather_labels.txt}"

echo "==> Installing Coral model to ${MODELS_DIR}"

sudo mkdir -p "${MODELS_DIR}"

if [[ -f "${MODELS_DIR}/weather_classify_edgetpu.tflite" ]]; then
    echo "Model already exists — skipping download.  Remove it to re-download."
else
    echo "Downloading model from ${MODEL_URL} …"
    sudo curl -fsSL -o "${MODELS_DIR}/weather_classify_edgetpu.tflite" "${MODEL_URL}"
    echo "Model downloaded."
fi

if [[ -f "${MODELS_DIR}/weather_labels.txt" ]]; then
    echo "Labels file already exists — skipping."
else
    echo "Downloading labels from ${LABELS_URL} …"
    sudo curl -fsSL -o "${MODELS_DIR}/weather_labels.txt" "${LABELS_URL}"
    echo "Labels downloaded."
fi

echo "==> Contents of ${MODELS_DIR}:"
ls -lh "${MODELS_DIR}"

echo ""
echo "Done.  The Pi Zero collector will look for these files automatically."
echo "Test with:  python -m Zweather.app_pizero"
