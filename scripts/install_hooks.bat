@echo off
REM Run once after git init to install pre-commit hook
REM Requires Git for Windows (Git Bash)

copy /Y scripts\check_secrets.sh .git\hooks\pre-commit
echo Pre-commit hook installed. Git Bash required.
