SET "BAT_ROOT_DIR=E:\script\bat"

CALL %BAT_ROOT_DIR%\nodejsconf.bat

CD frontend

CALL npm install -g

npm run dev