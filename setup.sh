#!/bin/bash
# Quick Setup Script for Data Processing Pipeline (Phase 1)

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Data Processing Pipeline (Phase 1) - Quick Setup           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Verify installation
echo ""
echo "Verifying installation..."
python3 -c "import pandas, numpy, yaml, tqdm, streamlit, plotly; print('✓ All dependencies installed successfully')"

# Create directories (if not exist)
echo ""
echo "Creating directories..."
mkdir -p outputs

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Setup Complete!                                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run Phase 1: python3 main.py"
echo "  3. View metrics in outputs/data_processing_stats.json"
echo "  4. Launch dashboard: streamlit run metrics_dashboard.py"
echo ""
