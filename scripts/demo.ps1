Param(
  [switch]$SkipInstall,
  [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Resolve-Path (Join-Path $root '..')
Set-Location $repo

Write-Host "[demo] repo: $repo"

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
  Write-Host "[demo] creating venv..."
  python -m venv .venv
}

Write-Host "[demo] activating venv..."
. .\.venv\Scripts\Activate.ps1

if (-not $SkipInstall) {
  Write-Host "[demo] installing deps..."
  pip install -r requirements.txt
  pip install -e .
}

New-Item -ItemType Directory -Force .\out | Out-Null

if (-not $SkipTests) {
  Write-Host "[demo] running quick tests..."
  python -m pytest -q
}

Write-Host "[demo] basic compile..."
promptc "teach me gradient descent in 15 minutes at intermediate level" --json-only --out .\out\ir_v2_basic.json | Out-Null

Write-Host "[demo] teaching mode..."
promptc "teach me binary search in 10 minutes beginner level" --json-only --out .\out\teach_mode.json | Out-Null

Write-Host "[demo] recency rule..."
promptc --from-file .\examples\example_recency_tr.txt --json-only --out .\out\recency.json | Out-Null

Write-Host "[demo] validate + fix..."
promptc validate-prompt "do something with stuff" --json | Out-Null
promptc fix "do something with stuff" --json | Out-Null

Write-Host "[demo] pack..."
promptc pack "Write a short tutorial about recursion" --format md --out .\out\prompt_pack.md | Out-Null

Write-Host "[demo] rag index + query..."
promptc rag index .\docs .\examples --ext .txt --ext .md | Out-Null
promptc rag query "gradient descent" --k 3 | Out-Null

Write-Host "[demo] done. outputs are in .\\out"
Write-Host "[demo] next: start API with: uvicorn api.main:app --reload"
