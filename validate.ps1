$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw 'Create .venv and install requirements-dev.txt before validating.'
    }
    $testTempPath = Join-Path $PSScriptRoot '.local-tmp'
    New-Item -ItemType Directory -Force -Path $testTempPath | Out-Null
    $originalTemp = $env:TEMP
    $originalTmp = $env:TMP
    try {
        $env:TEMP = $testTempPath
        $env:TMP = $testTempPath
        & $pythonPath -m pytest -q --basetemp .test-tmp @args
        $validationExit = $LASTEXITCODE
    } finally {
        $env:TEMP = $originalTemp
        $env:TMP = $originalTmp
    }
} finally {
    Pop-Location
}
exit $validationExit
