<#
.SYNOPSIS
  One-command publish for westbar.cn (Hexo -> GitHub Pages master).

.DESCRIPTION
  Builds the site, syncs public/ into a dedicated master working copy and
  pushes a NORMAL commit (keeps the existing 2015 commit history).

  By default this script does NOT force-push. Use -UseHexoDeploy only if you
  explicitly want hexo-deployer-git, which rewrites master history.

.EXAMPLE
  .\bin\publish.ps1
  .\bin\publish.ps1 -Message "add 2026 diary"
  .\bin\publish.ps1 -DryRun
#>
param(
  [string]$Message = "",
  [switch]$DryRun,
  [switch]$UseHexoDeploy
)

$ErrorActionPreference = "Stop"

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
$deployDir = Join-Path $root "_deploy"
$publicDir = Join-Path $root "public"

Write-Host "[1/4] Building site ..." -ForegroundColor Cyan
& npm run build
if ($LASTEXITCODE -ne 0) { throw "Hexo build failed. Publish aborted." }
if (-not (Test-Path (Join-Path $publicDir "index.html"))) {
  throw "public/index.html is missing. Publish aborted."
}

if ($DryRun) {
  Write-Host "DryRun: built into public/, nothing pushed." -ForegroundColor Yellow
  Write-Host "Preview with: npm run preview" -ForegroundColor Yellow
  return
}

if (-not $Message) { $Message = "site updated: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") }

if ($UseHexoDeploy) {
  Write-Host "[2/4] hexo deploy (WARNING: rewrites master history) ..." -ForegroundColor Yellow
  & npx hexo deploy
  if ($LASTEXITCODE -ne 0) { throw "hexo deploy failed." }
  Write-Host "[4/4] Done: https://www.westbar.cn" -ForegroundColor Green
  return
}

Write-Host "[2/4] Preparing master working copy ..." -ForegroundColor Cyan
if (-not $deployDir.EndsWith("_deploy")) { throw "Unexpected deploy dir: $deployDir" }

if (-not (Test-Path (Join-Path $deployDir ".git"))) {
  if (Test-Path $deployDir) {
    throw "$deployDir exists but is not a git repo. Remove it manually and retry."
  }
  & git clone --branch master $repoUrl $deployDir
  if ($LASTEXITCODE -ne 0) {
    throw "git clone failed. Check your SSH key / PAT (see README section 'Credentials')."
  }
}

Push-Location $deployDir
try {
  & git fetch origin master
  if ($LASTEXITCODE -ne 0) { throw "git fetch failed." }
  & git reset --hard origin/master | Out-Null

  Write-Host "[3/4] Syncing public/ and committing ..." -ForegroundColor Cyan
  Get-ChildItem -LiteralPath $deployDir -Force |
    Where-Object { $_.Name -ne ".git" } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

  Get-ChildItem -LiteralPath $publicDir -Force |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $deployDir -Recurse -Force }

  & git add -A
  $changed = & git status --porcelain
  if (-not $changed) {
    Write-Host "No content changes. Nothing to publish." -ForegroundColor Yellow
    return
  }

  & git commit -m $Message
  if ($LASTEXITCODE -ne 0) { throw "git commit failed. Configure user.name / user.email first." }

  & git push origin master
  if ($LASTEXITCODE -ne 0) { throw "git push failed." }
}
finally {
  Pop-Location
}

Write-Host "[4/4] Pushed. https://www.westbar.cn will update in ~1 minute." -ForegroundColor Green
