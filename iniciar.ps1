#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Porta = 8501
)

$ErrorActionPreference = 'Stop'
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$requirementsPath = Join-Path $PSScriptRoot 'requirements.txt'
$appPath = Join-Path $PSScriptRoot 'app.py'

Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath $projectPython)) {
        $pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($pythonLauncher) {
            & $pythonLauncher.Source -3 -m venv .venv
        }
        else {
            $pythonLauncher = Get-Command python.exe -ErrorAction SilentlyContinue
            if (-not $pythonLauncher) {
                throw 'Python nao encontrado. Instale Python 3.11 ou superior.'
            }
            & $pythonLauncher.Source -m venv .venv
        }
        if ($LASTEXITCODE -ne 0) {
            throw 'Nao foi possivel preparar o ambiente virtual.'
        }
    }

    $dependencyCheck = @'
import sys
try:
    import streamlit, pandas, google.genai, altair
except ImportError:
    sys.exit(1)
'@
    & $projectPython -c $dependencyCheck
    if ($LASTEXITCODE -ne 0) {
        & $projectPython -m pip install -r $requirementsPath
        if ($LASTEXITCODE -ne 0) {
            throw 'Nao foi possivel instalar as dependencias. Confira a conexao de rede.'
        }
    }

    Write-Host "Abra http://localhost:$Porta no navegador. Para encerrar, pressione Ctrl+C."
    & $projectPython -m streamlit run $appPath --server.headless true --server.address 127.0.0.1 --server.port $Porta
    if ($LASTEXITCODE -ne 0) {
        throw 'Nao foi possivel iniciar o TestingStudio. Confira as mensagens acima.'
    }
}
finally {
    Pop-Location
}
