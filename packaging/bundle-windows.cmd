@echo off
setlocal
set "TAURI_SIGNING_PRIVATE_KEY=%~1"
set "TAURI_SIGNING_PRIVATE_KEY_PASSWORD="
rtk proxy npm.cmd run tauri -- bundle --ci --bundles nsis --config src-tauri/tauri.updater.conf.json
set "bundle_result=%ERRORLEVEL%"
> "..\packaging\build\bundle-exit.txt" echo %bundle_result%
exit /b %bundle_result%
