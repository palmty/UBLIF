#!/bin/bash
# Shell script สำหรับรัน Streamlit Dashboard
# ใช้สำหรับ Linux/Mac

echo "============================================="
echo "   ACGI Data Processing Dashboard"
echo "============================================="
echo

# ตรวจสอบว่ามี virtual environment หรือไม่
if [ -d ".venv" ] && [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Warning: Virtual environment not found"
    echo "Using system Python..."
fi

# ตรวจสอบว่า Streamlit ติดตั้งแล้วหรือไม่
if ! python -c "import streamlit" 2>/dev/null; then
    echo "Installing required dependencies..."
    pip install -r requirements.txt
fi

# รัน Streamlit Dashboard
echo "Starting dashboard..."
echo "Dashboard จะเปิดใน browser อัตโนมัติ"
echo "URL: http://localhost:8501"
echo
echo "กด Ctrl+C เพื่อหยุด dashboard"
echo

streamlit run dashboard.py --server.port 8501 --server.address localhost