@echo off
REM Batch script สำหรับรัน Streamlit Dashboard
REM ใช้สำหรับ Windows

echo =============================================
echo   ACGI Data Processing Dashboard
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

REM รัน Streamlit Dashboard
echo Starting dashboard...
echo Dashboard จะเปิดใน browser อัตโนมัติ
echo URL: http://localhost:8501
echo.
echo กด Ctrl+C เพื่อหยุด dashboard
echo.

%PYTHON_PATH% -m streamlit run dashboard.py --server.port 8501 --server.address localhost

pause