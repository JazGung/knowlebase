set "BAT_ROOT_DIR=E:\script\bat"
set "ROOT_DIR=%~dp0"

echo %ROOT_DIR%

@REM 启动中间件
docker compose -f %~dp0docker-compose-midware.yml -p knowlebase up -d

@REM 启动后端
CALL "%BAT_ROOT_DIR%\execute_cmd_in_new_tab.bat" "%ROOT_DIR%" "CALL %~dp0\startup-backend.bat" "Backend"

@REM 启动前端
CALL "%BAT_ROOT_DIR%\execute_cmd_in_new_tab.bat" "%ROOT_DIR%" "CALL %~dp0\startup-frontend.bat" "Frontend"
