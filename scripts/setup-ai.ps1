$ErrorActionPreference = 'Stop'
$trainingProjectRoot = Split-Path -Parent $PSScriptRoot
$trainingPython = Join-Path $trainingProjectRoot '.venv-ai/Scripts/python.exe'
$existingProjectPython = Join-Path $trainingProjectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $trainingPython)) {
    & $existingProjectPython -m venv (Join-Path $trainingProjectRoot '.venv-ai')
    if ($LASTEXITCODE -ne 0) { throw 'AI environment creation failed' }
}
& $trainingPython -m pip --version
if ($LASTEXITCODE -ne 0) {
    & $trainingPython -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw 'AI pip setup failed' }
}
& $trainingPython -m pip install --only-binary=:all: -r (Join-Path $trainingProjectRoot 'ai/requirements-ai.txt')
if ($LASTEXITCODE -ne 0) { throw 'AI dependency installation failed' }
& $trainingPython -c "import torch, torchvision; print('torch',torch.__version__,'torchvision',torchvision.__version__,'CUDA available',torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw 'AI runtime import check failed' }
