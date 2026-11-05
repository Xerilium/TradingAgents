@echo off
cd D:\src\TradingAgents
npm.cmd --prefix "%~dp0desktop" run tauri -- dev --config src-tauri/tauri.dev.conf.json
pause