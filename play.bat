@echo off
chcp 65001 >nul
rem Запуск игры одним кликом: сервер разработки и открытие в браузере.
rem Закройте это окно, чтобы остановить игру.
cd /d "%~dp0"
title Червь-Пожиратель (разработка)

rem Node.js мог быть установлен только что, и проводник ещё не знает новый PATH
where node >nul 2>nul || set "PATH=%PATH%;%ProgramFiles%\nodejs"
where node >nul 2>nul
if errorlevel 1 (
  echo Не найден Node.js. Установите версию LTS с https://nodejs.org и запустите игру снова.
  pause
  exit /b 1
)

if not exist node_modules (
  echo Первый запуск: ставлю пакеты, это займёт минуту...
  call npm install --no-audit --no-fund
  if errorlevel 1 (
    echo Не удалось поставить пакеты. Проверьте интернет и запустите снова.
    pause
    exit /b 1
  )
)

node tools\dev.mjs --open
pause
