# 🧪 测试原则 - 数据安全第一

## 🚨 绝对禁止的行为

### ❌ 永远不要在生产数据库上测试！

#### 禁止测试的数据库
- `portfolio.db` - 主生产数据库
- `backend/data/portfolio.db` - 数据目录中的生产库
- 任何包含真实交易、持仓、价格数据的数据库
- **一旦在生产库测试，可能导致数据不可逆损坏！**

#### 后果警告
```
❌ 测试数据混入生产环境
❌ 真实持仓数据被污染  
❌ 历史交易记录错乱
❌ 投资组合计算结果失真
❌ 数据恢复困难或不可能
```

## ✅ 正确的测试环境

### 专用测试数据库
```bash
# 方法1：环境变量指定
export PORT_DB_PATH="/path/to/test.db"

# 方法2：代码中明确指定
pytest --db-path="test.db"

# 方法3：配置文件设置
test_db_path: "test_portfolio.db"
```

### 测试数据库特征
- ✅ 独立的SQLite文件
- ✅ 包含测试种子数据
- ✅ 可安全删除和重建
- ✅ 与生产数据完全隔离

## 测试环境设置

### 1. 数据库隔离
```python
# 测试配置示例
def setup_test_database():
    test_db_path = "test_portfolio.db"
    # 确保使用测试数据库
    os.environ['PORT_DB_PATH'] = test_db_path
    
    # 初始化测试数据
    init_test_schema()
    load_test_seeds()
```

### 2. 测试数据准备
```python
# 标准测试数据
TEST_INSTRUMENTS = [
    {"ts_code": "000001.SZ", "name": "平安银行", "type": "STOCK"},
    {"ts_code": "159919.SZ", "name": "沪深300ETF", "type": "ETF"}
]

TEST_TRANSACTIONS = [
    {"ts_code": "000001.SZ", "action": "BUY", "qty": 1000, "price": 10.0}
]
```

### 3. 测试清理
```python
def teardown_test():
    # 清理测试数据
    if os.path.exists("test_portfolio.db"):
        os.remove("test_portfolio.db")
    
    # 重置环境变量
    if 'PORT_DB_PATH' in os.environ:
        del os.environ['PORT_DB_PATH']
```

## 测试分类和策略

### 1. 单元测试
- **范围**: 单个函数或类的逻辑
- **数据库**: Mock或内存数据库
- **示例**: 交易引擎计算、价格解析逻辑

```python
def test_transaction_engine():
    # 纯逻辑测试，不涉及真实数据库
    result = compute_position_after_trade(
        old_shares=100, old_avg_cost=10.0,
        action="SELL", qty=50, price=15.0, fee=2.0
    )
    assert result == (50, 10.0, 248.0)
```

### 2. 集成测试
- **范围**: Service层与Repository层交互
- **数据库**: 专用测试数据库
- **示例**: 价格同步、持仓计算

```python  
def test_price_sync_integration():
    # 使用测试数据库
    setup_test_database()
    
    # 测试完整流程
    result = sync_prices_enhanced(lookback_days=3)
    
    # 验证结果
    assert result['total_updated'] > 0
    
    # 清理测试数据
    teardown_test()
```

### 3. 端到端测试
- **范围**: 完整API请求响应
- **数据库**: 独立测试实例
- **示例**: HTTP接口测试

## 测试数据管理

### 1. 测试数据原则
- **最小化**: 只包含测试必需的数据
- **可重复**: 每次测试结果一致
- **隔离性**: 测试间不相互影响
- **真实性**: 模拟真实业务场景

### 2. 数据清理策略
```python
class TestDataManager:
    def setup(self):
        """测试前：准备干净的测试环境"""
        self.ensure_test_db()
        self.load_minimal_data()
    
    def teardown(self):
        """测试后：清理所有测试痕迹"""
        self.clear_all_test_data()
        self.verify_production_untouched()
```

### 3. 数据完整性检查
```python
def verify_data_integrity():
    """验证测试没有影响生产数据"""
    prod_db = get_production_db()
    
    # 检查关键表的记录数
    assert get_table_count(prod_db, 'transactions') == EXPECTED_PROD_COUNT
    assert get_table_count(prod_db, 'positions') == EXPECTED_PROD_COUNT
```

## pytest最佳实践

### 1. 测试组织
```
backend/tests/
├── conftest.py           # 测试配置和fixtures
├── test_transaction_engine.py  # 交易引擎测试
├── test_pricing_service.py     # 价格服务测试
├── test_api_endpoints.py       # API端点测试
└── data/                       # 测试数据文件
```

### 2. Fixtures使用
```python
@pytest.fixture
def test_db():
    """提供测试数据库连接"""
    db_path = "test_temp.db"
    setup_test_database(db_path)
    yield get_connection(db_path)
    cleanup_test_database(db_path)

@pytest.fixture  
def sample_transactions():
    """提供标准测试交易数据"""
    return load_test_transactions()
```

### 3. 运行测试
```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest backend/tests/test_pricing_service.py

# 显示详细输出
pytest -v

# 测试覆盖率
pytest --cov=backend
```

## 测试安全检查表

### 每次测试前确认
- [ ] 确认使用的是测试数据库路径
- [ ] 检查环境变量 `PORT_DB_PATH` 设置
- [ ] 验证没有连接到生产数据库
- [ ] 准备充分的测试数据

### 每次测试后验证
- [ ] 清理所有测试产生的数据
- [ ] 验证生产数据库未被修改
- [ ] 重置所有环境变量
- [ ] 删除临时测试文件

**记住：测试的第一原则是不伤害生产环境！**