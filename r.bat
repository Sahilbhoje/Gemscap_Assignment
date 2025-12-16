@echo off
setlocal
"%~dp0.venv\Scripts\python.exe" "%~dp0extract_pdf_text.py" "%~dp0Quant_Developer_Assignment_Anagh_6 (2) (2) (2) - Copy.pdf" "%~dp0assignment_instructions.txt"
endlocal