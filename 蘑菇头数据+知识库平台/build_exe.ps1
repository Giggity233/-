<#
Build a portable Windows server package. Run from the project root:
    powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onedir --name 'LianzunServer' `
    --add-data 'templates;templates' `
    --add-data 'static;static' `
    --add-data 'core/templates;core/templates' `
    --add-data 'core/migrations;core/migrations' `
    --collect-submodules core `
    --collect-submodules lianzun `
    --collect-all waitress `
    --hidden-import pymysql `
    --hidden-import MySQLdb `
    --hidden-import django.db.backends.mysql `
    run_server.py

$packageDir = Join-Path $projectRoot 'dist\LianzunServer'
Copy-Item (Join-Path $projectRoot 'server.env.example') (Join-Path $packageDir 'server.env') -Force
Get-ChildItem -Path $projectRoot -Filter '*.md' | Copy-Item -Destination $packageDir -Force
$zipPath = Join-Path $projectRoot 'dist\LianzunServer.zip'
Compress-Archive -Path $packageDir -DestinationPath $zipPath -Force

Write-Host "Package created: $packageDir"
Write-Host "ZIP created: $zipPath"
Write-Host 'Set DJANGO_ALLOWED_HOSTS in server.env, then run LianzunServer.exe.'
