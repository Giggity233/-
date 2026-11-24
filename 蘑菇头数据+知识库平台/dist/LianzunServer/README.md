# 蘑菇头中控平台

## 启动（MySQL）

1. 创建 MySQL 数据库：`CREATE DATABASE lianzun DEFAULT CHARACTER SET utf8mb4;`
2. 安装依赖：`pip install -r requirements.txt`
3. 在 PowerShell 设置数据库与接口密钥：

```powershell
$env:MYSQL_DATABASE='lianzun'
$env:MYSQL_USER='root'
$env:MYSQL_PASSWORD='你的数据库密码'
$env:MYSQL_HOST='127.0.0.1'
$env:MYSQL_PORT='3306'
```

4. 执行：

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

首次创建的超级管理员可访问“权限管理中心”，为普通用户配置预置角色。数据库采用 MySQL；仅为本机界面体验可设置 `$env:USE_SQLITE='1'` 后运行迁移。

接口无需请求头或接口密钥。详情参见 [接口文档.md](接口文档.md)，版本记录参见 [更新日志.md](更新日志.md)。

> 注意：由于当前需求明确要求采集接口不做鉴权，请仅将服务部署在受信任内网，或通过防火墙限制可访问本机 `8000` 端口的来源。

## Windows 服务器 EXE 部署

1. 在 MySQL 中创建数据库：`CREATE DATABASE lianzun DEFAULT CHARACTER SET utf8mb4;`
2. 在项目目录执行：`powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`。
3. 将生成的 `dist\LianzunServer` 整个文件夹复制到服务器（不可只复制 EXE）。
4. 编辑文件夹中的 `server.env`：默认 MySQL 用户为 `root`、密码为 `123456`。默认可通过服务器 IP 访问；如需进一步限制访问，可将 `DJANGO_ALLOWED_HOSTS` 改成服务器实际 IP 或域名。
5. 双击 `LianzunServer.exe`。首次启动会自动执行数据库迁移，并创建管理员 `guangon1`；初始密码为 `heyiwei111`。

首次创建之后，管理员密码不会因重启而被覆盖。若确实需要重置，可在命令行运行：`LianzunServer.exe --reset-admin-password`。

首次启动还会在 EXE 旁生成 `server.secret`，用于保持 Django 登录会话安全；请不要删除或公开该文件。
