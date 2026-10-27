@echo off
setlocal
set "CARGO_BUILD_JOBS=2"
rtk proxy npm.cmd run tauri -- build --debug --no-bundle --ci --config src-tauri/tauri.dev.conf.json
set "build_result=%ERRORLEVEL%"
> "..\packaging\build\dev-exit.txt" echo %build_result%
exit /b %build_result%
