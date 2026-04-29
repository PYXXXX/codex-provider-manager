param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CliArgs
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Stamp = Join-Path $Venv ".cpm-installed"
$NeedsInstall = $false

function Fail-With-Pause {
    param([string] $Message)
    Write-Host ""
    Write-Host "codex-provider-manager failed: $Message" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

function Test-CpmVenv {
    if (-not (Test-Path $Python)) { return $false }
    if (-not (Test-Path (Join-Path $Venv "pyvenv.cfg"))) { return $false }
    & $Python -c "import codex_provider_manager" *> $null
    return ($LASTEXITCODE -eq 0)
}

function New-CpmVenv {
    $script:NeedsInstall = $true
    if (Test-Path $Venv) {
        try {
            Remove-Item -LiteralPath $Venv -Recurse -Force -ErrorAction Stop
        } catch {
            $Fallback = Join-Path $Root ".venv-run"
            Write-Host "Could not replace .venv because it is in use. Using .venv-run instead." -ForegroundColor Yellow
            $script:Venv = $Fallback
            $script:Python = Join-Path $script:Venv "Scripts\python.exe"
            $script:Stamp = Join-Path $script:Venv ".cpm-installed"
            if (Test-Path $script:Venv) {
                Remove-Item -LiteralPath $script:Venv -Recurse -Force -ErrorAction Stop
            }
        }
    }
    python -m venv $script:Venv
}

try {
    if (-not (Test-CpmVenv)) {
        New-CpmVenv
    }

    if ($NeedsInstall -or -not (Test-Path $Stamp)) {
        & $Python -m pip install -e "$Root"
        if ($LASTEXITCODE -ne 0) { Fail-With-Pause "pip install failed" }
        New-Item -ItemType File -Path $Stamp -Force | Out-Null
    }

    if ($CliArgs.Count -eq 0) {
        & $Python -m codex_provider_manager.cli tui
    } else {
        & $Python -m codex_provider_manager.cli @CliArgs
    }
    if ($LASTEXITCODE -ne 0) { Fail-With-Pause "command exited with code $LASTEXITCODE" }
} catch {
    Fail-With-Pause $_.Exception.Message
}
