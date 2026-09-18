$ErrorActionPreference = 'Stop'
$python = 'python'
$version = & $python -c 'import sys; print(sys.version_info >= (3, 10))'
if ($version -ne 'True') {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path $bundled)) { throw 'Python 3.10–3.12 is required.' }
    $python = $bundled
}
if (-not (Test-Path '.venv\Scripts\python.exe')) { & $python -m venv .venv }
& .venv\Scripts\python.exe -m pip install -r requirements.txt
& .venv\Scripts\python.exe -m uvicorn chemimage.app:app --host 127.0.0.1 --port 8000