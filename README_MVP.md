# Care Plan MVP — 最小可运行流程

前端表单 → 提交 → 后端同步调用 OpenAI (gpt-4o-mini) → 返回并展示 Care Plan。数据存内存，无数据库。

## 运行

1. 设置 OpenAI API Key：
   ```bash
   export OPENAI_API_KEY=sk-your-key
   ```
   或复制 `.env.example` 为 `.env` 并填入 `OPENAI_API_KEY`，再用 `docker-compose --env-file .env up`。

2. 用 Docker 启动：
   ```bash
   docker-compose up --build
   ```

3. 浏览器打开 http://localhost:8000 ，填写表单后点 “Generate Care Plan”，等待几秒即可在页面下方看到生成的 care plan。

## 不用 Docker 时

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-your-key
python manage.py runserver
```

然后访问 http://127.0.0.1:8000 。
