@echo off
setlocal
cd /d %~dp0
if exist .env (
  echo A .env file already exists.
  choice /M "Overwrite it"
  if errorlevel 2 exit /b 0
)
set /p AISKEY=Paste your AISStream API key: 
if "%AISKEY%"=="" (
  echo No key entered. Nothing was changed.
  exit /b 1
)
> .env echo AISSTREAM_API_KEY=%AISKEY%
echo AISStream key saved in .env. This file is excluded from Git.
echo Restart Streamlit to activate Maritime Intelligence.
pause
