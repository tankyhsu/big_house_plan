# 🏗️ 架构分层原则 - 系统设计核心

## 严格分层架构

### 层次职责定义
```
API层 (routes/) → Service层 (services/) → Repository层 (repository/) → Database
     ↓                ↓                      ↓                    ↓
HTTP处理         业务逻辑处理           数据访问逻辑          SQLite存储
```

### ❌ 严禁违反的架构规则

#### 1. Service层绝不直接访问数据库
```python
# 🚫 错误示例 - 永远不要这样做！
def some_service_function():
    from ..db import get_conn  # 违反架构分层
    with get_conn() as conn:
        return conn.execute("SELECT * FROM table").fetchall()
```

#### 2. Repository层不处理业务逻辑
```python
# 🚫 错误示例 - Repository层不应包含业务规则
def get_user_data(conn, user_id):
    # 这里不应该有业务逻辑判断
    if is_premium_user(user_id):  # 业务逻辑应在Service层
        return get_premium_data()
```

### ✅ 正确的分层实现

#### Service层标准模式
```python
def enhanced_price_sync(lookback_days: int = 7) -> dict:
    """Service层：纯业务逻辑处理"""
    # 1. 调用Repository获取数据
    from ..repository import price_repo
    missing_data = price_repo.find_missing_price_dates(conn, lookback_days)
    
    # 2. 业务逻辑处理
    if not missing_data:
        return {"message": "所有数据完整"}
    
    # 3. 协调多个Repository完成业务流程
    sync_results = []
    for date in missing_data:
        result = orchestrate_sync(date)
        sync_results.append(result)
        
    return aggregate_results(sync_results)
```

#### Repository层标准模式
```python
def find_missing_price_dates(conn, lookback_days: int) -> dict:
    """Repository层：纯数据访问"""
    # SQL查询和数据转换
    sql = """
    SELECT trade_date, ts_code 
    FROM active_instruments ai
    LEFT JOIN price_eod pe ON ai.ts_code = pe.ts_code 
        AND pe.trade_date >= ?
    WHERE pe.ts_code IS NULL
    """
    
    results = conn.execute(sql, [start_date]).fetchall()
    return transform_to_business_format(results)
```

## 分层设计原则

### 1. 单一职责原则
- **API层**: 只处理HTTP请求响应，参数验证
- **Service层**: 只处理业务逻辑，不涉及数据访问细节
- **Repository层**: 只处理数据访问，不包含业务规则
- **Domain层**: 核心业务实体和规则

### 2. 依赖倒置原则
- 高层模块(Service)不依赖低层模块(Database)
- 通过Repository抽象层解耦
- Service层通过接口调用Repository

### 3. 关注点分离
```python
# API层：HTTP关注点
@router.post("/api/sync-prices-enhanced")  
def api_sync_prices_enhanced(body: dict):
    # 参数验证和HTTP响应处理
    return service_layer_call()

# Service层：业务关注点  
def sync_prices_enhanced():
    # 业务流程编排和逻辑处理
    return repository_calls()
    
# Repository层：数据关注点
def find_missing_data(conn):
    # SQL查询和数据映射
    return database_results()
```

## 重构指导原则

### 识别违反架构的代码
1. Service层中出现 `from ..db import get_conn`
2. Service层中直接写SQL语句
3. Repository层中包含复杂业务判断
4. API层直接调用数据库

### 重构步骤
1. **抽取Repository方法**: 将数据访问逻辑移到repository层
2. **清理Service层**: 移除所有数据库访问代码
3. **明确接口**: 定义清晰的Service-Repository接口
4. **测试验证**: 确保重构后功能正常

### 新功能开发规范
1. 先设计Repository接口
2. 实现Repository数据访问
3. 编写Service业务逻辑
4. 添加API端点
5. 编写测试用例

## 架构收益

### 1. 可维护性
- 职责清晰，问题定位准确
- 修改影响面小，降低风险
- 代码复用性高

### 2. 可测试性  
- Service层可独立测试业务逻辑
- Repository层可独立测试数据访问
- Mock依赖简单

### 3. 可扩展性
- 数据库切换只影响Repository层
- 业务逻辑变更不影响数据访问
- API版本升级不影响核心逻辑

### 4. 团队协作
- 不同层次可并行开发
- 接口约定清晰
- 代码review更高效

**记住：架构分层不是负担，而是长期维护的基础！**