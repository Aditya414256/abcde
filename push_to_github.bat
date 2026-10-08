@echo off
echo ===================================================
echo   MediFind - Push to GitHub
echo ===================================================
echo.
cd /d "%~dp0"
echo Current Directory: %CD%
echo Pushing branch 'main' to https://github.com/kasarpratik185-svg/Medifinder_Project.git ...
echo.
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] Code successfully pushed to GitHub!
) else (
    echo [FAILED] Git push failed. If prompted, please sign in with GitHub or use a Personal Access Token.
)
echo.
pause
