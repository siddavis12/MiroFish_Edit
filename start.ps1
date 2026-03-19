# MiroFish 실행 스크립트
# Neo4j / 백엔드 / 프론트엔드를 각각 별도 터미널 창으로 실행
# 사전 요구사항: Node.js >= 18, Python 3.11~3.12, uv

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
chcp 65001 | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MiroFish 실행 스크립트" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ============== 1. 사전 요구사항 확인 ==============

$missing = @()

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  $missing += "Node.js (>= 18)"
} else {
  Write-Host "[OK] Node.js $(node -v)" -ForegroundColor Green
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  $missing += "Python (3.11 ~ 3.12)"
} else {
  Write-Host "[OK] $(python --version)" -ForegroundColor Green
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  $missing += "uv (Python 패키지 관리자)"
} else {
  Write-Host "[OK] $(uv --version)" -ForegroundColor Green
}

if ($missing.Count -gt 0) {
  Write-Host ""
  Write-Host "[오류] 다음 도구가 설치되어 있지 않습니다:" -ForegroundColor Red
  $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
  exit 1
}

# ============== 2. .env 파일 확인 ==============

$envFile = Join-Path $ProjectRoot ".env"
$envExample = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $envFile)) {
  if (Test-Path $envExample) {
    Write-Host ""
    Write-Host "[경고] .env 파일이 없습니다. .env.example에서 복사합니다." -ForegroundColor Yellow
    Copy-Item $envExample $envFile
    Write-Host "[안내] $envFile 에 LLM_API_KEY를 설정한 후 다시 실행하세요." -ForegroundColor Yellow
    exit 1
  } else {
    Write-Host "[경고] .env 파일이 없습니다. 환경변수 오류가 발생할 수 있습니다." -ForegroundColor Yellow
  }
}

# ============== 3. 의존성 설치 ==============

Write-Host ""
Write-Host ">> 의존성 설치 중..." -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $ProjectRoot "node_modules"))) {
  Write-Host "  루트 npm install..." -ForegroundColor Gray
  Push-Location $ProjectRoot
  $ErrorActionPreference = "Continue"
  $null = & npm install --legacy-peer-deps 2>&1
  $ErrorActionPreference = "Stop"
  Pop-Location
}

$frontendDir = Join-Path $ProjectRoot "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
  Write-Host "  프론트엔드 npm install..." -ForegroundColor Gray
  Push-Location $frontendDir
  $ErrorActionPreference = "Continue"
  $null = & npm install --legacy-peer-deps 2>&1
  $ErrorActionPreference = "Stop"
  Pop-Location
}

Write-Host "  백엔드 uv sync..." -ForegroundColor Gray
Push-Location (Join-Path $ProjectRoot "backend")
$ErrorActionPreference = "Continue"
$uvOutput = & uv sync 2>&1
$uvExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($uvExit -ne 0) {
  Write-Host "[오류] uv sync 실패:" -ForegroundColor Red
  $uvOutput | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
  Pop-Location
  exit 1
}
Pop-Location

Write-Host "[OK] 의존성 설치 완료" -ForegroundColor Green

# ============== 4. 터미널 창 실행 헬퍼 ==============

# Windows Terminal(wt)이 있으면 새 탭으로, 없으면 새 PowerShell 창으로 실행
function Start-ScriptWindow {
  param(
    [string]$ScriptPath,
    [string]$Label
  )

  $args = "-ExecutionPolicy Bypass -File `"$ScriptPath`" -ProjectRoot `"$ProjectRoot`""
  $wtAvailable = $null -ne (Get-Command wt -ErrorAction SilentlyContinue)

  if ($wtAvailable) {
    Start-Process wt -ArgumentList "new-tab powershell $args"
  } else {
    Start-Process powershell -ArgumentList $args
  }

  Write-Host "  [열림] $Label" -ForegroundColor White
}

# ============== 5. Neo4j 실행 ==============

Write-Host ""
$neo4jBat = Join-Path $ProjectRoot "neo4j\bin\neo4j.bat"

if (Test-Path $neo4jBat) {
  # 이미 실행 중인지 확인
  $neo4jRunning = $false
  try {
    $conn = New-Object System.Net.Sockets.TcpClient
    $conn.Connect("localhost", 7687)
    $conn.Close()
    $neo4jRunning = $true
  } catch {}

  if ($neo4jRunning) {
    Write-Host "[OK] Neo4j 이미 실행 중 (bolt://localhost:7687)" -ForegroundColor Green
  } else {
    Start-ScriptWindow -ScriptPath (Join-Path $ProjectRoot "run-neo4j.ps1") -Label "Neo4j 창 열림"

    # 준비 대기 (최대 30초)
    Write-Host ">> Neo4j 시작 대기 중..." -ForegroundColor Cyan
    $waited = 0
    while ($waited -lt 30) {
      Start-Sleep -Seconds 2
      $waited += 2
      try {
        $conn = New-Object System.Net.Sockets.TcpClient
        $conn.Connect("localhost", 7687)
        $conn.Close()
        $neo4jRunning = $true
        break
      } catch {}
      Write-Host "  대기 중... ($waited/30 초)" -ForegroundColor Gray
    }

    if ($neo4jRunning) {
      Write-Host "[OK] Neo4j 연결 확인됨" -ForegroundColor Green
    } else {
      Write-Host "[경고] Neo4j 시작 시간 초과 — 창을 직접 확인하세요." -ForegroundColor Yellow
    }
  }
} else {
  Write-Host "[경고] Neo4j 미설치 — setup-neo4j.ps1 을 먼저 실행하세요." -ForegroundColor Yellow
}

# ============== 6. 백엔드 실행 ==============

Write-Host ""
Start-ScriptWindow -ScriptPath (Join-Path $ProjectRoot "run-backend.ps1") -Label "백엔드 창 열림 (:5001)"

# ============== 7. 프론트엔드 실행 ==============

Start-ScriptWindow -ScriptPath (Join-Path $ProjectRoot "run-frontend.ps1") -Label "프론트엔드 창 열림 (:3000)"

# ============== 8. 완료 안내 ==============

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MiroFish 서비스 시작 완료" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  프론트엔드 : http://localhost:3000" -ForegroundColor Cyan
Write-Host "  백엔드     : http://localhost:5001" -ForegroundColor Green
Write-Host "  Neo4j      : http://localhost:7474" -ForegroundColor Magenta
Write-Host ""
Write-Host "  종료 방법" -ForegroundColor Yellow
Write-Host "    개별 종료 : 각 창에서 Ctrl+C" -ForegroundColor Gray
Write-Host "    전체 종료 : .\stop.ps1 실행" -ForegroundColor Gray
Write-Host ""
Write-Host "  이 창은 닫아도 됩니다." -ForegroundColor DarkGray
