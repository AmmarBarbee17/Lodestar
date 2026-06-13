<#
.SYNOPSIS
  Single command surface for the thesis repo.

.DESCRIPTION
  Wraps the Quarto render pipeline + PM tooling under one entry point so
  nobody memorizes script paths. Run `.\thesis.ps1 help` for the table.
  Non-Windows users call the underlying python scripts directly -- every
  subcommand below names the script it wraps (see README.md).

  NOTE: keep this file pure ASCII -- PowerShell 5.1 reads BOM-less
  scripts as ANSI and garbles multi-byte characters.

.EXAMPLE
  .\thesis.ps1 render                 # HTML site (satellites cached)
  .\thesis.ps1 render force           # ... re-render every satellite
  .\thesis.ps1 render pdf             # include the LaTeX PDF build
  .\thesis.ps1 render-one A5-EX-002   # one satellite, fast inner loop
  .\thesis.ps1 new experiment --epic A5 --slug head-cad --title "..."
  .\thesis.ps1 audit --fix
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = "help",

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest = @()
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if ($null -eq $Rest) { $Rest = @() }

function Assert-Venv {
    if (-not (Test-Path $Py)) {
        Write-Host "Python venv missing. Bootstrap once with:" -ForegroundColor Yellow
        Write-Host "  py -3.12 -m venv .venv"
        Write-Host "  .venv\Scripts\python.exe -m pip install -r requirements.txt"
        exit 1
    }
}

function Invoke-Tool {
    param([string]$Script, [string[]]$ToolArgs = @())
    Assert-Venv
    & $Py (Join-Path $Root "scripts\render\$Script") @ToolArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-PreRenderHooks {
    Invoke-Tool "build_listings.py"
    Invoke-Tool "build_gantt.py"
    Invoke-Tool "build_file_trees.py"
    Invoke-Tool "build_revisions.py"
    Invoke-Tool "build_board.py"
}

function Initialize-GeneratedPartials {
    # Quarto expands book-page includes (_board.md, chapters'
    # _revisions-*.md) at CONFIG time -- before pre-render hooks run --
    # so a fresh clone's first render fails unless the partials exist.
    # _board.md is the sentinel: missing => prime all generators once.
    if (-not (Test-Path (Join-Path $Root "_board.md"))) {
        Write-Host "priming generated partials (fresh clone)..."
        Invoke-PreRenderHooks
    }
}

switch ($Command.ToLower()) {

    "render" {
        # Default is HTML-only: the PDF pass is a slow LaTeX build that
        # belongs in pre-publish runs, not the inner loop.
        Initialize-GeneratedPartials
        $force = ($Rest -contains "force") -or ($Rest -contains "-force")
        $pdf = ($Rest -contains "pdf") -or ($Rest -contains "-pdf")
        if ($pdf) { quarto render } else { quarto render --to html }
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($force) { Invoke-Tool "render_satellites.py" @("--force") }
    }

    "render-one" {
        if ($Rest.Count -eq 0) {
            Write-Host "usage: .\thesis.ps1 render-one <path-or-substring>"
            Write-Host "  chapters/...qmd renders via quarto; anything else"
            Write-Host "  matches a satellite (e.g. A5-EX-002, WU-2026-05-29)"
            exit 1
        }
        Invoke-PreRenderHooks
        $target = $Rest[0]
        if (($target -replace "\\", "/") -like "chapters/*") {
            quarto render $target
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        else {
            Invoke-Tool "render_satellites.py" @("--only", $target, "--force")
        }
    }

    "preview" {
        Initialize-GeneratedPartials
        quarto preview
    }

    "publish" { Invoke-Tool "publish.py" $Rest }
    "audit" { Invoke-Tool "audit_items.py" $Rest }
    "new" { Invoke-Tool "new_item.py" $Rest }
    "disperse" { Invoke-Tool "disperse.py" $Rest }
    "gantt" { Invoke-Tool "build_gantt.py" $Rest }
    "board" { Invoke-Tool "build_board.py" $Rest }
    "revisions" { Invoke-Tool "build_revisions.py" $Rest }
    "listings" { Invoke-Tool "build_listings.py" $Rest }

    "cache-clear" {
        $cache = Join-Path $Root ".quarto\satellite-cache"
        if (Test-Path $cache) {
            Remove-Item -Recurse -Force $cache
            Write-Host "satellite cache cleared (next render rebuilds all)"
        }
        else {
            Write-Host "satellite cache already empty"
        }
    }

    "doctor" {
        $ok = $true
        if (Test-Path $Py) {
            Write-Host "[ok]   venv: $Py"
        }
        else {
            Write-Host "[FAIL] venv missing: py -3.12 -m venv .venv; .venv\Scripts\python.exe -m pip install -r requirements.txt"
            $ok = $false
        }
        $quarto = Get-Command quarto -ErrorAction SilentlyContinue
        if ($quarto) {
            Write-Host "[ok]   quarto: $($quarto.Source)"
        }
        else {
            Write-Host "[FAIL] quarto not on PATH: install from quarto.org"
            $ok = $false
        }
        $hooks = git -C $Root config core.hookspath
        if ($hooks -eq "scripts/git-hooks") {
            Write-Host "[ok]   git hooks: $hooks"
        }
        else {
            Write-Host "[FAIL] git hooks: run  git config core.hooksPath scripts/git-hooks"
            $ok = $false
        }
        $longpaths = git -C $Root config core.longpaths
        if ($longpaths -eq "true") {
            Write-Host "[ok]   git longpaths: true"
        }
        else {
            Write-Host "[FAIL] long paths: run  git config core.longpaths true"
            $ok = $false
        }
        $lfs = Get-Command git-lfs -ErrorAction SilentlyContinue
        if ($lfs) {
            Write-Host "[ok]   git-lfs: $($lfs.Source)"
        }
        else {
            Write-Host "[FAIL] git-lfs missing: install, then  git lfs install --skip-repo"
            $ok = $false
        }
        if (-not $ok) { exit 1 }
        Initialize-GeneratedPartials
        Write-Host "doctor: all checks green"
    }

    default {
        Write-Host @"
thesis.ps1 -- command surface for the thesis repo (docs: docs/README.md)

  render [pdf] [force]     HTML site; satellites cached. force = rebuild all
                           satellites; pdf = include the LaTeX build
  render-one <target>      one page fast: chapters/...qmd, or a satellite
                           substring (A5-EX-002, WU-2026-05-29)
  preview                  quarto preview (live reload for book pages)
  publish                  audit -> render -> link check -> gh-pages
                           (scripts/render/publish.py)
  new <kind> ...           scaffold experiment|feature|issue|epic|wu
                           (scripts/render/new_item.py --help for flags)
  audit [--fix] [--owner]  front-matter contract check
                           (scripts/render/audit_items.py)
  disperse [...]           stage `$THESIS_INBOX -> _inbox/<week>/
                           (scripts/render/disperse.py; then /disperse skill)
  gantt [--force]          per-WU frozen Gantt PNGs (build_gantt.py)
  board [--stale-weeks N]  dashboard kanban + stale items (build_board.py)
  revisions                git change-history partials (build_revisions.py)
  listings                 listing.yml + _listing.md partials (build_listings.py)
  cache-clear              wipe .quarto/satellite-cache
  doctor                   verify venv / quarto / git hooks / lfs setup
"@
    }
}
