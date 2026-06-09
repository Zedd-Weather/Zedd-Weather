#!/usr/bin/env bash
"""
Zedd Weather — Investor Demo Setup
===================================
One-command setup for investor testing of the Zedd Weather platform.
"""
set -euo pipefail

echo "☁  Zedd Weather — Investor Demo Setup"
echo "======================================="
echo ""

# ── Check Python version ──────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python)
PYVER=$("$PYTHON" --version 2>&1 | grep -oP '\d+\.\d+')
echo "[1/5] Python $PYVER detected ($PYTHON)"

# ── Create virtual environment ────────────────────────────────────────────────
if [ ! -d .venv ]; then
    echo "[2/5] Creating virtual environment..."
    "$PYTHON" -m venv .venv
else
    echo "[2/5] Virtual environment already exists."
fi

source .venv/bin/activate

# ── Install dependencies ──────────────────────────────────────────────────────
echo "[3/5] Installing dependencies..."
pip install -q --upgrade pip setuptools wheel
pip install -q -r Zweather/requirements.txt
pip install -q -e .

# ── Run tests ─────────────────────────────────────────────────────────────────
echo "[4/5] Running test suite..."
"$PYTHON" -m pytest Zweather/tests/ -q --tb=short 2>&1 | tail -5
echo ""

# ── Demo: run all sectors ─────────────────────────────────────────────────────
echo "[5/5] Running demo analysis across all 8 sectors..."
echo ""

TELEMETRY="--temperature 18.5 --humidity 72 --pressure 1008 --wind-speed 6.2 --precipitation 35"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Multi-Sector Weather Risk Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
$PYTHON -m Zweather.cli batch $TELEMETRY --output summary
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Single-Sector Deep Dive: Aviation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
$PYTHON -m Zweather.cli analyze aviation $TELEMETRY --visibility-m 5000 --activity commercial_jet --output summary
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  With Regional Adjustment: Glasgow in Winter"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
$PYTHON -m Zweather.cli analyze construction $TELEMETRY --region glasgow --season winter --output summary
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  REST API (start with: uvicorn Zweather.api:app)"
echo "  Dashboard   (start with: python -m Zweather.dashboard.app)"
echo "  CLI         (start with: zedd --help)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅  Setup complete. All systems operational."
echo ""
