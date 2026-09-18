# 广告会员后台

这是一个以 FastAPI + SQLAlchemy + PostgreSQL 为目标部署栈的广告会员运营后台。当前已经包含仪表盘、主体、游戏、会员、广告、提现、补贴、金币流水和风控列表，并支持主体/游戏/会员基础 CRUD 以及提现、补贴审核流转；广告列表按主广 / 副广口径展示，并支持详情查看、CSV 导入导出、导入异常追踪、广告统计报表和广告告警。

## 本地运行

安装 Python 依赖：

```powershell
python -m pip install -r backend/requirements.txt
```

复制环境变量模板，并按需修改：

```powershell
Copy-Item .env.example .env
```

直接运行时默认使用 `backend/app.db` 作为 SQLite 演示库：

```powershell
python backend/run.py
```

访问 <http://localhost:8000>，接口文档在 <http://localhost:8000/docs>。

也可以单独启动静态后台壳子：

```powershell
npm run dev
```

访问 <http://localhost:3000>。此方式会把 `/api/*` 请求代理到 `http://127.0.0.1:8000`，因此仍需先运行 `python backend/run.py`；如后端地址不同，可设置 `BACKEND_ORIGIN`。

开发环境默认管理员为 `admin`，密码为 `Admin123!`。首次部署后应立即通过环境变量或改密接口修改密码；业务接口需要登录后携带 Bearer 令牌访问。

## PostgreSQL

启动本地 PostgreSQL 容器：

```powershell
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://ad_member:ad_member_dev@localhost:5432/ad_member"
python backend/run.py
```

数据库连接由 `DATABASE_URL` 控制。正式环境还必须设置 `APP_ENV=production`、`JWT_SECRET` 和 `ADMIN_PASSWORD`。迁移命令：

```powershell
alembic -c alembic.ini upgrade head
```

开发环境启动时仍会创建缺失表并写入一组演示数据，正式环境应在部署阶段先执行迁移，并替换演示数据初始化逻辑。

## Docker Compose

先复制并修改环境变量：

```powershell
Copy-Item .env.example .env
```

至少需要修改 `.env` 中的 `JWT_SECRET`、`ADMIN_PASSWORD`、`POSTGRES_PASSWORD` 和 `DATABASE_URL`。其中 `DATABASE_URL` 的密码要与 `POSTGRES_PASSWORD` 保持一致。

启动数据库和应用：

```powershell
docker compose up -d --build
```

应用容器启动时会先执行：

```powershell
alembic -c /app/alembic.ini upgrade head
```

然后启动 FastAPI 服务。访问 <http://localhost:8000>，接口文档在 <http://localhost:8000/docs>。

只启动 PostgreSQL：

```powershell
docker compose up -d postgres
```

## 测试

测试使用临时 SQLite 数据库，不会修改本地演示库：

```powershell
python -m unittest discover -s backend/tests -v
python -m py_compile backend/app/main.py backend/tests/test_core_crud.py backend/run.py
npm run check
```

## 目录

- `backend/app/main.py`：数据模型、接口、初始化数据和静态文件服务
- `backend/tests/test_core_crud.py`：核心 CRUD 与审核流转测试
- `backend/alembic/versions/`：数据库迁移基线
- `public/index.html`、`public/app.js`、`public/styles.css`：后台管理界面
- `docker-compose.yml`：本地 PostgreSQL 服务
- `.env.example`：环境变量模板
- `Dockerfile`、`docker-entrypoint.sh`：容器化应用启动

核心接口前缀为 `/api/v1`。主体、游戏、会员支持 `GET / POST / PATCH / DELETE`；提现支持审核通过、驳回和标记转账；补贴支持通过和驳回。
