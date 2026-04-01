@echo off
REM Batch script สำหรับรัน Data Processing Metrics Evaluation Dashboard
REM ใช้สำหรับ Windows

echo =============================================
echo   Data Processing Metrics Evaluation 
echo =============================================
echo.

REM ตรวจสอบว่ามี virtual environment หรือไม่
if exist ".venv\Scripts\python.exe" (
    echo Activating virtual environment...
    set PYTHON_PATH="%CD%\.venv\Scripts\python.exe"
) else (
    echo Warning: Virtual environment not found
    echo Using system Python...
    set PYTHON_PATH=python
)

REM ตรวจสอบว่า Streamlit ติดตั้งแล้วหรือไม่
%PYTHON_PATH% -c "import streamlit" 2>nul
if errorlevel 1 (
    echo Installing required dependencies...
    %PYTHON_PATH% -m pip install -r requirements.txt
)

REM รัน Metrics Dashboard
echo Starting Data Processing Metrics Dashboard...
echo Dashboard จะเปิดใน browser อัตโนมัติ
echo URL: http://localhost:8502
echo.
echo กด Ctrl+C เพื่อหยุด dashboard
echo.

%PYTHON_PATH% -m streamlit run metrics_dashboard.py --server.port 8502 --server.address localhost

pause