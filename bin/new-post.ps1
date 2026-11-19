<#
.SYNOPSIS
  Create a new diary post and open it in your editor.

.EXAMPLE
  .\bin\new-post.ps1 -Title "Today's diary"
  .\bin\new-post.ps1 -Title "Weekly notes" -NoOpen
#>
param(
  [Parameter(Mandatory = $true)][string]$Title,
  [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$postsDir = Join-Path $root "source\_posts"

$before = @(Get-ChildItem -LiteralPath $postsDir -Filter "*.md" | ForEach-Object { $_.FullName })

& npx hexo new post $Title
if ($LASTEXITCODE -ne 0) { throw "hexo new failed." }

$new = @(Get-ChildItem -LiteralPath $postsDir -Filter "*.md" |
         Where-Object { $before -notcontains $_.FullName } |
         Sort-Object LastWriteTime -Descending)

if ($new.Count -eq 0) {
  Write-Host "Created, but could not locate the new file. Check source\_posts\." -ForegroundColor Yellow
  return
}

$file = $new[0].FullName
Write-Host ""
Write-Host "New post: $file" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Edit the file above (Markdown)."
Write-Host "  2. npm run preview        -> open http://localhost:4000"
Write-Host "  3. .\bin\publish.ps1 -> publish to westbar.cn"
Write-Host ""

if (-not $NoOpen) {
  $code = Get-Command code -ErrorAction SilentlyContinue
  if ($code) { & code $file }
  else { & notepad $file }
}
