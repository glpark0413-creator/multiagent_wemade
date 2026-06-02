@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo  ==========================================
echo   멀티 에이전트 PM  ^|  http://localhost:5050
echo  ==========================================
echo.
echo  [AI 설정]
echo  Ollama 사용: 아래 두 줄의 주석을 해제하고 맥북 IP를 입력하세요.
echo.
echo.

:: ── Ollama 설정 ──────────────────────────────────────────────────────
set OLLAMA_HOST=http://localhost:11434
set OLLAMA_MODEL=qwen2.5:7b

:: ── Claude API 설정 (Ollama 미사용 시) ──────────────────────────────
:: set ANTHROPIC_API_KEY=sk-ant-...

python server.py
pause
