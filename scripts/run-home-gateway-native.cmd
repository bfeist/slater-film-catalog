@echo off
setlocal

rem Run the home video gateway on Windows so ffmpeg reads the mapped archive
rem directly instead of through Docker Desktop's slow network-filesystem path.
for %%I in ("%~dp0..") do set "GATEWAY_ROOT=%%~fI"

set "NODE_ENV=production"
set "PROJECT_ROOT=%GATEWAY_ROOT%"
set "DB_PATH=%GATEWAY_ROOT%\database\catalog.db"
set "SHOTLIST_PDF_DIR=%GATEWAY_ROOT%\static_assets\shotlist_pdfs"
set "VIDEO_ARCHIVE_ROOT=O:\"
set "LOG_DIR=%GATEWAY_ROOT%\.local\gatewayLogs"
set "VIDEO_ENCODER=h264_nvenc"
set "WATERMARK_FONT_PATH=C:\Windows\Fonts\arial.ttf"
set "WATERMARK_MONO_FONT_PATH=C:\Windows\Fonts\consola.ttf"

title Slater Home Video Gateway - Native NVENC
pushd "%GATEWAY_ROOT%\.local\express"
node --env-file="%GATEWAY_ROOT%\.env.home" dist\gateway.js
set "GATEWAY_EXIT=%ERRORLEVEL%"
popd

echo.
echo Gateway exited with code %GATEWAY_EXIT%.
pause
exit /b %GATEWAY_EXIT%
