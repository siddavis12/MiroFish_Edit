# MiroFish - 백엔드 실행 창
# start.ps1에 의해 별도 터미널로 열림. 직접 실행도 가능.

param(
  [string]$ProjectRoot = $PSScriptRoot
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
chcp 65001 | Out-Null
$host.UI.RawUI.WindowTitle = "MiroFish | 백엔드 :5001"

$backendDir = Join-Path $ProjectRoot "backend"

if (-not (Test-Path $backendDir)) {
  Write-Host "[오류] backend 디렉토리를 찾을 수 없습니다: $backendDir" -ForegroundColor Red
  Read-Host "Enter 키를 눌러 닫기"
  exit 1
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "  MiroFish | 백엔드" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  URL  : http://localhost:5001" -ForegroundColor Gray
Write-Host "  종료 : Ctrl+C  (또는 stop.ps1)" -ForegroundColor Gray
Write-Host ""

Set-Location $backendDir

try {
  uv run python run.py
} finally {
  Write-Host ""
  Write-Host "[OK] 백엔드 프로세스 종료됨" -ForegroundColor Green
  Write-Host "이 창을 닫으세요." -ForegroundColor Gray
}
