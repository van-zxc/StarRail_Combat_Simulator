# GitHub 上传指引 (Agent 专用)

> 当用户要求将当前仓库上传到 GitHub 时使用。

## 步骤

### 1. 确认 git config

```
git config --global user.name
git config --global user.email
```

若未配置，向用户索要并执行：
```
git config --global user.name "<用户名>"
git config --global user.email "<邮箱>"
```

### 2. 初始化仓库（若尚未 init）

```
git init
```

### 3. 创建/更新 .gitignore

排除以下内容：
- `__pycache__/`, `*.pyc`, `.pytest_cache/`
- `.agent_memory`, `AGENT_LOG.md`, `AGENTS`
- `test_starrail_combat.py`, `test_elation.py`
- `original_data/`, `docs/`

### 4. 通知用户在 GitHub 建仓库

告诉用户：
1. 打开 https://github.com/new
2. Repository name: 用户指定的名称
3. **不要勾选** README / .gitignore / license
4. 点击 Create repository

### 5. 提交并推送

```
git add -A
git commit -m "<简要描述改动>"
git remote add origin https://github.com/<用户名>/<仓库名>.git
git push -u origin main
```

### 6. 推送后确认

- 打开 `https://github.com/<用户名>/<仓库名>` 验证
- 确认不应上传的文件（test/dsocs/original_data）未出现在仓库中

### 注意事项

- 绝不上传测试文件（`test_*.py`）
- 绝不上传 `docs/` / `original_data/` 目录
- 绝不上传 `__pycache__` / `.pytest_cache` / `.agent_memory`
- 提交信息使用用户语言（中文）
- 若推送失败（权限/auth），检查：是否已建仓库、remote URL 是否正确、是否需要 personal access token
