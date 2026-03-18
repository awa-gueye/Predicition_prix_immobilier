@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM  Configuration du Planificateur de tâches Windows
REM  Lance scrape_scheduler.py tous les jours à 02:00
REM
REM  USAGE : Exécuter ce fichier en tant qu'ADMINISTRATEUR
REM  (clic droit -> "Exécuter en tant qu'administrateur")
REM ─────────────────────────────────────────────────────────────────────────────

REM Adapter ces deux chemins à ton installation
SET PROJECT_DIR=C:\Users\hp\Documents\AS3_2025-2026\SEMESTRE_1\Program_django\Projet1_immoblier
SET PYTHON=%PROJECT_DIR%\env\Scripts\python.exe

REM Supprimer l'ancienne tâche si elle existe
schtasks /delete /tn "ImmobilierScraping" /f 2>nul

REM Créer la tâche planifiée
schtasks /create ^
  /tn "ImmobilierScraping" ^
  /tr "\"%PYTHON%\" \"%PROJECT_DIR%\scrape_scheduler.py\"" ^
  /sc DAILY ^
  /st 02:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

IF %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Tâche planifiée créée avec succès !
    echo    Nom    : ImmobilierScraping
    echo    Heure  : 02:00 chaque nuit
    echo    Script : %PROJECT_DIR%\scrape_scheduler.py
    echo.
    echo Pour vérifier : ouvrir "Planificateur de tâches" dans Windows
) ELSE (
    echo.
    echo ❌ Erreur lors de la création de la tâche.
    echo    Assurez-vous d'exécuter ce fichier en tant qu'Administrateur.
)

pause
