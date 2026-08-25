#!/usr/bin/env bash
# ============================================================
# GSEA Dashboard - Local Development Startup Script
# Starts both the Streamlit frontend and FastAPI backend
# Usage: bash run_dev.sh
# ============================================================

set -e

echo ""
echo "🌿 Starting GSEA Dashboard (Development Mode)"
echo "============================================="
echo ""

# Check Python
python --version || { echo "❌ Python not found"; exit 1; }

# Check virtual environment
if [ ! -d "venv" ]; then
    echo "⚠️  No venv found. Creating..."
    python -m venv venv
fi

source venv/bin/activate 2>/dev/null || . venv/Scripts/activate 2>/dev/null || true

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt -q

# Copy .env if not present
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚙️  Created .env from .env.example (review and edit as needed)"
fi

# Generate sample data
echo "📊 Generating sample data..."
python scripts/generate_sample_data.py

# Run tests
echo ""
echo "🧪 Running test suite..."
python -m pytest tests/ -v --tb=short
echo ""

# Start FastAPI backend in background
echo "🚀 Starting FastAPI backend on http://localhost:8000"
echo "   API docs: http://localhost:8000/docs"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
sleep 2

# Start Streamlit frontend
echo ""
echo "🌿 Starting Streamlit dashboard on http://localhost:8501"
echo ""
streamlit run app.py

# Cleanup on exit
trap "kill $API_PID 2>/dev/null; echo 'Stopped.'" EXIT
