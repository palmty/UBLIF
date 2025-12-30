#!/bin/bash
# Quick Setup Script for Hybrid Recommendation System

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Hybrid Recommendation System - Quick Setup                 ║"
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
python3 -c "import pandas, numpy, mlxtend, networkx, sklearn, matplotlib, seaborn, yaml; print('✓ All dependencies installed successfully')"

# Create directories (if not exist)
echo ""
echo "Creating directories..."
mkdir -p outputs
mkdir -p visualizations
mkdir -p tests

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Setup Complete!                                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run the pipeline: python3 main.py --phase all"
echo "  3. View results in outputs/evaluation_report.html"
echo ""
