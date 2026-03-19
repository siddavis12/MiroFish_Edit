# MiroFish - 프론트엔드 실행 창
# start.ps1에 의해 별도 터미널로 열림. 직접 실행도 가능.

param(
  [string]$ProjectRoot = $PSScriptRoot
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$host.UI.RawUI.WindowTitle = "MiroFish | 프론트엔드 :3000"

$frontendDir = Join-Path $ProjectRoot "frontend"

if (-not (Test-Path $frontendDir)) {
  Write-Host "[오류] frontend 디렉토리를 찾을 수 없습니다: $frontendDir" -ForegroundColor Red
  Read-Host "Enter 키를 눌러 닫기"
  exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MiroFish | 프론트엔드" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  URL  : http://localhost:3000" -ForegroundColor Gray
Write-Host "  종료 : Ctrl+C  (또는 stop.ps1)" -ForegroundColor Gray
Write-Host ""

Set-Location $frontendDir

try {
  npm run dev
} finally {
  Write-Host ""
  Write-Host "[OK] 프론트엔드 프로세스 종료됨" -ForegroundColor Green
  Write-Host "이 창을 닫으세요." -ForegroundColor Gray
}
