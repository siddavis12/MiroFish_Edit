# MiroFish 프론트엔드 + 백엔드 실행 스크립트
# 사전 요구사항: Node.js >= 18, Python 3.11~3.12, uv

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MiroFish 실행 스크립트" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 사전 요구사항 확인
$missing = @()

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  $missing += "Node.js (>= 18)"
} else {
  $nodeVer = (node -v)
  Write-Host "[OK] Node.js $nodeVer" -ForegroundColor Green
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  $missing += "Python (3.11 ~ 3.12)"
} else {
  $pyVer = (python --version)
  Write-Host "[OK] $pyVer" -ForegroundColor Green
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  $missing += "uv (Python 패키지 관리자)"
} else {
  $uvVer = (uv --version)
  Write-Host "[OK] $uvVer" -ForegroundColor Green
}

if ($missing.Count -gt 0) {
  Write-Host ""
  Write-Host "[오류] 다음 도구가 설치되어 있지 않습니다:" -ForegroundColor Red
  $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
  exit 1
}

# Neo4j 실행 여부 확인
$neo4jBat = Join-Path $ProjectRoot "neo4j\bin\neo4j.bat"
if (Test-Path $neo4jBat) {
  try {
    $conn = New-Object System.Net.Sockets.TcpClient
    $conn.Connect("localhost", 7687)
    $conn.Close()
    Write-Host "[OK] Neo4j (bolt://localhost:7687)" -ForegroundColor Green
  } catch {
    Write-Host "[경고] Neo4j가 설치되어 있지만 실행 중이 아닙니다" -ForegroundColor Yellow
    Write-Host "       별도 터미널에서 실행: .\start-neo4j.ps1" -ForegroundColor Yellow
  }
} else {
  Write-Host "[경고] Neo4j 미설치 — 설정: .\setup-neo4j.ps1" -ForegroundColor Yellow
}

# .env 파일 확인
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
    Write-Host ""
    Write-Host "[경고] .env 파일이 없습니다. 백엔드 실행 시 환경변수 오류가 발생할 수 있습니다." -ForegroundColor Yellow
  }
}

# 의존성 설치
Write-Host ""
Write-Host ">> 의존성 설치 중..." -ForegroundColor Cyan

# 루트 node_modules
if (-not (Test-Path (Join-Path $ProjectRoot "node_modules"))) {
  Write-Host "  루트 npm install..." -ForegroundColor Gray
  Push-Location $ProjectRoot
  $ErrorActionPreference = "Continue"
  $null = & npm install --legacy-peer-deps 2>&1
  $ErrorActionPreference = "Stop"
  Pop-Location
}

# 프론트엔드 node_modules
$frontendDir = Join-Path $ProjectRoot "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
  Write-Host "  프론트엔드 npm install..." -ForegroundColor Gray
  Push-Location $frontendDir
  $ErrorActionPreference = "Continue"
  $null = & npm install --legacy-peer-deps 2>&1
  $ErrorActionPreference = "Stop"
  Pop-Location
}

# 백엔드 Python 의존성
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

# 프론트엔드 & 백엔드 동시 실행
Write-Host ""
Write-Host ">> 서버 시작 중..." -ForegroundColor Cyan
Write-Host "  백엔드:    http://localhost:5001" -ForegroundColor Green
Write-Host "  프론트엔드: http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "종료하려면 Ctrl+C를 누르세요." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

# concurrently로 프론트엔드 + 백엔드 동시 실행 (양쪽 로그 모두 표시)
Push-Location $ProjectRoot
try {
  npm run dev
} finally {
  Pop-Location
}
