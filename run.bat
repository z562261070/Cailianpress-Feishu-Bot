@echo off
chcp 65001 >nul
echo ========================================
echo 财联社电报飞书Bot推送工具
echo ========================================
echo.

echo 请选择操作:
echo 1. 运行主程序 (抓取电报 + 飞书推送)
echo 2. 仅生成5天整合文件
echo 3. 测试飞书Bot配置
echo 4. 设置环境变量
echo 5. 退出
echo.

set /p choice=请输入选择 (1-5): 

if "%choice%"=="1" (
    echo.
    echo 正在运行主程序...
    python cls_to_feishu.py
    goto end
)

if "%choice%"=="2" (
    echo.
    echo 正在生成5天整合文件...
    python cls_to_feishu.py --summary
    goto end
)

if "%choice%"=="3" (
    echo.
    echo 正在测试飞书Bot配置...
    python test_feishu_bot.py
    goto end
)

if "%choice%"=="4" (
    echo.
    echo 设置飞书Bot环境变量:
    echo.
    set /p app_id=请输入 FEISHU_APP_ID: 
    set /p app_secret=请输入 FEISHU_APP_SECRET: 
    set /p chat_id=请输入 FEISHU_CHAT_ID: 
    
    set FEISHU_APP_ID=%app_id%
    set FEISHU_APP_SECRET=%app_secret%
    set FEISHU_CHAT_ID=%chat_id%
    set ENABLE_FEISHU_BOT=true
    
    echo.
    echo ✅ 环境变量设置完成 (仅在当前会话有效)
    echo.
    echo 如需永久设置，请手动添加到系统环境变量或使用以下命令:
    echo setx FEISHU_APP_ID "%app_id%"
    echo setx FEISHU_APP_SECRET "%app_secret%"
    echo setx FEISHU_CHAT_ID "%chat_id%"
    echo setx ENABLE_FEISHU_BOT "true"
    echo.
    goto menu
)

if "%choice%"=="5" (
    echo 再见!
    goto end
)

echo 无效选择，请重新输入
echo.

:menu
echo.
echo 按任意键返回主菜单...
pause >nul
cls
goto start

:start
goto :eof

:end
echo.
echo 按任意键退出...
pause >nul