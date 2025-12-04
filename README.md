# 敲可爱战队 · 炉石传说竞技场战队官网

基于 FastAPI + Jinja2 + SQLAlchemy + SQL Server 的全栈项目，包含：

- 用户注册 / 登录（JWT）
- 战队成员资料 / 成就
- 竞技场攻略 / 评论
- 卡牌评测
- 管理员后台
- 首页 3D 英雄展示区

## 环境准备

1. 安装 Python 3.10+
2. 安装 SQL Server，并创建数据库（例如 `qiaoketai_db`）
3. 安装 ODBC 驱动（Windows 下通常自带 `ODBC Driver 17 for SQL Server`）

## 安装依赖

```bash
pip install -r requirements.txt
