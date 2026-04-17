title Knowlebase Backend

set "BAT_ROOT_DIR=E:\script\bat"

set "ROOT_DIR=%~dp0"

CALL %BAT_ROOT_DIR%\pythonconf.bat

CD backend

pip install -r requirements.txt

SET PYTHONPATH=%ROOT_DIR%\backend\src

SET DEBUG=true

uvicorn knowlebase.main:app --reload --host 0.0.0.0 --port 8000