<#
.SYNOPSIS
  One-time setup: init the Hexo SOURCE repo on branch `hexo`, set the remote,
  and verify GitHub SSH access.

.DESCRIPTION
  The GitHub repo only contains the BUILT site on master. This script keeps
  your Hexo source (config, theme, posts) on a separate `hexo` branch so it
  survives a machine change. Publishing still targets master via publish.ps1.

.EXAMPLE
  .\bin\setup.ps1
  .\bin\setup.ps1 -Push
#>
param([switch]$Push)

$ErrorActionPreference = "Continue"

# git.exe is not on PATH in this environment; auto-locate common installs.
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  $gitDirs = @(
    "D:\Program Files\WorkBuddy\resources\vendor\PortableGit\mingw64\bin",
    "D:\Program Files\WorkBuddy\resources\vendor\PortableGit\cmd",
    "$env:ProgramFiles\Git\cmd",
    "${env:ProgramFiles(x86)}\Git\cmd",
    "$env:LOCALAPPDATA\Programs\Git\cmd"
  )
  foreach ($gdir in $gitDirs) {
    if (Test-Path (Join-Path $gdir "git.exe")) {
      $env:PATH = $gdir + [IO.Path]::PathSeparator + $env:PATH
      break
    }
  }
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git.exe not found. Install Git for Windows: https://git-scm.com/download/win"
}

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$repoUrl = "git@github.com:hnustluyu/hnustluyu.github.io.git"

Write-Host "== westbar.cn Hexo source setup ==" -ForegroundColor Cyan
Write-Host "Working dir: $root"
Write-Host ""

# 1. git identity (local identity is enough; do not overwrite user's global config)
$name = & git config user.name
$mail = & git config user.email
if (-not $name -or -not $mail) {
  Write-Host "[!] git identity is not configured. Run these first:" -ForegroundColor Yellow
  Write-Host '    git config user.name  "hnustluyu"'
  Write-Host '    git config user.email "hnustluyu@users.noreply.github.com"'
  Write-Host ""
}

# 2. init repo
if (-not (Test-Path (Join-Path $root ".git"))) {
  & git init
  if ($LASTEXITCODE -ne 0) { throw "git init failed." }
  Write-Host "[ok] git init" -ForegroundColor Green
} else {
  Write-Host "[ok] git repo already exists" -ForegroundColor Green
}

# 3. remote
$existing = (& git remote get-url origin 2>$null); if ($LASTEXITCODE -ne 0) { $existing = $null }
if (-not $existing) {
  & git remote add origin $repoUrl
  Write-Host "[ok] remote origin -> $repoUrl" -ForegroundColor Green
} else {
  Write-Host "[ok] remote origin = $existing" -ForegroundColor Green
}

# 4. stage + commit on branch hexo
& git add -A
$staged = & git diff --cached --name-only
if ($staged) {
  & git commit -m "init: Hexo source restored from westbar.cn static snapshot"
  if ($LASTEXITCODE -ne 0) { throw "git commit failed (check git identity above)." }
  Write-Host "[ok] initial commit created" -ForegroundColor Green
} else {
  Write-Host "[ok] nothing to commit" -ForegroundColor Green
}
& git branch -M hexo
Write-Host "[ok] active branch: hexo (master stays for the built site)" -ForegroundColor Green

# 5. SSH check (informational: GitHub returns exit code 1 on success)
Write-Host ""
Write-Host "Checking SSH access to GitHub (expect: Hi hnustluyu! ...):" -ForegroundColor Cyan
& ssh -T -o StrictHostKeyChecking=accept-new git@github.com 2>&1 | ForEach-Object { Write-Host "    $_" }
Write-Host ""

if ($Push) {
  Write-Host "Pushing source branch hexo ..." -ForegroundColor Cyan
  & git push -u origin hexo
  if ($LASTEXITCODE -ne 0) { throw "push failed. Fix credentials, then rerun with -Push." }
  Write-Host "[ok] source backed up on GitHub branch hexo" -ForegroundColor Green
} else {
  Write-Host "To back up the source now, run:  .\bin\setup.ps1 -Push" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next: check GitHub > Settings > Pages > Build from branch: master / root" -ForegroundColor Cyan
Write-Host "      then:  .\bin\new-post.ps1 -Title 'My first diary'" -ForegroundColor Cyan
