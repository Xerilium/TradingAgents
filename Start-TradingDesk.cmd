@echo off
setlocal
set "DESK_EXE=%LOCALAPPDATA%\TradingAgents\tradingagents-desktop.exe"
if not exist "%DESK_EXE%" set "DESK_EXE=%LOCALAPPDATA%\Programs\TradingAgents\tradingagents-desktop.exe"
if not exist "%DESK_EXE%" (
  echo Install TradingAgents before using this launcher.
  exit /b 1
)
start "" "%DESK_EXE%"
