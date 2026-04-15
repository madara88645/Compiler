param(
    [switch]$IncludeDeleteCommands
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-GitLines {
    param([string[]]$Arguments)

    $output = & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }

    return @($output | Where-Object { $_ -and $_.Trim() })
}

function Write-Section {
    param([string]$Title)

    Write-Output ""
    Write-Output "== $Title =="
}

$originMain = "refs/remotes/origin/main"
$currentBranch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "git branch --show-current failed with exit code $LASTEXITCODE"
}

$remoteMerged = @(Get-GitLines @("branch", "-r", "--merged", $originMain) |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and $_ -notmatch "^origin/(main|HEAD)" })

$remoteUnmerged = @(Get-GitLines @("branch", "-r", "--no-merged", $originMain) |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and $_ -notmatch "^origin/(main|HEAD)" })

$worktreeBranches = @(Get-GitLines @("worktree", "list", "--porcelain") |
    Where-Object { $_ -match "^branch refs/heads/" } |
    ForEach-Object { $_ -replace "^branch refs/heads/", "" })

$localMerged = @(Get-GitLines @(
        "for-each-ref",
        "refs/heads",
        "--merged=$originMain",
        "--format=%(refname:short)"
    ) |
    Where-Object { $_ -and $_ -ne "main" -and $_ -ne $currentBranch })

$localDirectDelete = @($localMerged | Where-Object { $worktreeBranches -notcontains $_ })
$localBlockedByWorktree = @($localMerged | Where-Object { $worktreeBranches -contains $_ })

$localGone = @(Get-GitLines @("branch", "-vv") |
    Where-Object { $_ -match ": gone\]" } |
    ForEach-Object { ($_ -replace "^\s*[+*]?\s*", "").Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)[0] })

$prunableWorktrees = @(& git worktree prune --dry-run -v 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw "git worktree prune --dry-run -v failed with exit code $LASTEXITCODE"
}

Write-Section "Merged remote branches"
Write-Output "Count: $($remoteMerged.Count)"
$remoteMerged | ForEach-Object { Write-Output $_ }

if ($IncludeDeleteCommands) {
    Write-Section "Merged remote delete commands"
    $remoteMerged |
        ForEach-Object { $_ -replace "^origin/", "" } |
        ForEach-Object { Write-Output "git push origin --delete $_" }
}

Write-Section "Merged local branches not attached to worktrees"
Write-Output "Count: $($localDirectDelete.Count)"
$localDirectDelete | ForEach-Object { Write-Output $_ }

if ($IncludeDeleteCommands) {
    Write-Section "Merged local delete commands"
    $localDirectDelete | ForEach-Object { Write-Output "git branch -d $_" }
}

Write-Section "Merged local branches blocked by worktrees"
Write-Output "Count: $($localBlockedByWorktree.Count)"
$localBlockedByWorktree | ForEach-Object { Write-Output $_ }

Write-Section "Local branches with gone upstream"
Write-Output "Count: $($localGone.Count)"
$localGone | ForEach-Object { Write-Output $_ }

Write-Section "Remote branches not merged into origin/main"
Write-Output "Count: $($remoteUnmerged.Count)"
$remoteUnmerged | ForEach-Object { Write-Output $_ }

Write-Section "Prunable worktree metadata"
if ($prunableWorktrees.Count -eq 0) {
    Write-Output "None"
} else {
    $prunableWorktrees | ForEach-Object { Write-Output $_ }
}
