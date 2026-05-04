# Pre-commit guard for Windows (PowerShell)
# Install: copy to .git\hooks\pre-commit (no extension) with content below

$staged = git diff --cached --name-only

$blocked = @('\.env$', 'profile\.json$', 'kb\.json$')
foreach ($pattern in $blocked) {
    $match = $staged | Where-Object { $_ -match $pattern }
    if ($match) {
        Write-Host "BLOCKED: attempting to commit sensitive file: $match" -ForegroundColor Red
        Write-Host "Run: git reset HEAD $match"
        exit 1
    }
}

$diff = git diff --cached
if ($diff -match '(sk-[a-zA-Z0-9]{20,}|AIza[a-zA-Z0-9_-]{35,}|sk-ant-)') {
    Write-Host "BLOCKED: staged diff appears to contain an API key." -ForegroundColor Red
    exit 1
}

exit 0
