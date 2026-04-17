title Knowlebase Frontend

SET "BAT_ROOT_DIR=E:\script\bat"

CALL %BAT_ROOT_DIR%\nodejsconf.bat

CD %~dp0frontend

CALL npm install -g

npm run dev