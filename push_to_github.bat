@echo off
echo ===================================================
echo   MediFind - Push to GitHub
echo ===================================================
echo.
cd /d "%~dp0"
echo Current Directory: %CD%
echo Pushing branch 'main' to https://github.com/Aditya414256/abcde.git ...
echo.
git push -u abcde main
echo.
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Code successfully pushed to GitHub repository!
) else (
    echo [FAILED] Git push failed. If prompted, please sign in with GitHub or use a Personal Access Token.
)
echo.
pause
