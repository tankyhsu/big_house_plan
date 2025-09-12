# 🚨 关键原则 - 必须严格遵守

## 1. 架构分层原则 (最重要!)

### ❌ 严禁：Service层直接访问数据库
```python
# 错误示例 - 永远不要这样做
def some_service_function():
    from ..db import get_conn
    with get_conn() as conn:
        conn.execute("SELECT * FROM table")
```

### ✅ 正确：Service层调用Repository层
```python
# 正确示例 - 必须这样做
def some_service_function():
    from ..repository import some_repo
    return some_repo.get_data()
```

### 分层职责
- **Service层 (`backend/services/`)**: 纯业务逻辑，不碰数据库
- **Repository层 (`backend/repository/`)**: 专门数据访问，SQL查询
- **API层 (`backend/routes/`)**: HTTP处理，调用Service层

## 2. 测试安全原则 (绝对禁止!)

### ❌ 永远不要在生产数据库上测试
- `portfolio.db` - 禁止测试
- `backend/data/portfolio.db` - 禁止测试
- 任何包含真实业务数据的数据库 - 禁止测试

### ✅ 必须使用测试数据库
- `test.db` - 专用测试数据库
- 设置 `PORT_DB_PATH` 环境变量指向测试DB
- 测试后清理所有数据

### 测试黄金法则
**测试必须是：安全的、隔离的、可重复的！**

## 3. 代码修改原则

### 优先级顺序
1. 编辑现有文件 > 创建新文件
2. 复用现有逻辑 > 重复编写
3. Repository模式 > 直接数据库访问
4. 测试验证 > 假设正确

### 禁止行为
- 不要在Service层写SQL
- 不要创建不必要的新文件  
- 不要在生产环境测试
- 不要忽略架构分层

## 重要提醒
这些原则是代码质量和数据安全的基础，违反这些原则可能导致：
- 数据损坏或丢失
- 系统架构混乱
- 代码难以维护
- 测试不可靠

**请严格遵守这些原则！**