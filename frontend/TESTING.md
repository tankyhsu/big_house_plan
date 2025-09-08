# Frontend Testing Guide

## 测试框架设置

项目使用以下测试工具栈：

- **Vitest**: 现代化的测试运行器，与 Vite 完美集成
- **React Testing Library**: React 组件测试库
- **jsdom**: 浏览器环境模拟
- **@testing-library/jest-dom**: 增强的 DOM 断言

## 测试脚本

```bash
# 运行所有测试
npm run test

# 运行测试并生成覆盖率报告
npm run test:run

# 开启 UI 界面运行测试
npm run test:ui
```

## 测试覆盖范围

### 1. 工具函数测试 (`src/utils/`)
- ✅ `format.ts` - 数据格式化函数
- ✅ `signalConfig.ts` - 信号配置工具

### 2. API 客户端测试 (`src/api/`)
- ✅ `client.ts` - Axios 客户端配置和拦截器
- ✅ `hooks.ts` - API 调用钩子函数

### 3. 组件测试 (`src/components/`)
- ✅ `KpiCards.tsx` - KPI 卡片组件
- ✅ `PositionTable.tsx` - 持仓表格组件

### 4. 图表组件测试 (`src/components/charts/`)
- ✅ `PositionPie.tsx` - 持仓饼图组件
- ✅ `HistoricalLineChart.tsx` - 历史趋势图组件

## 测试配置

### Vitest 配置 (`vite.config.ts`)
```typescript
test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
}
```

### 测试环境设置 (`src/test/setup.ts`)
- 导入 `@testing-library/jest-dom`
- Mock `window.matchMedia` (Ant Design 需要)
- Mock `window.getComputedStyle` (RC 组件需要)
- Mock `ResizeObserver` (图表组件需要)

## 测试策略

### 1. 工具函数测试
- 测试各种输入场景（正常值、null、undefined、边界值）
- 测试格式化输出的正确性
- 测试配置对象的完整性

### 2. API 测试
- Mock Axios 实例和方法
- 测试请求参数的正确性
- 测试响应数据的处理
- 测试错误处理机制

### 3. 组件测试
- 测试组件渲染的正确性
- 测试 props 传递和显示
- 测试用户交互（点击、输入等）
- 测试条件渲染逻辑
- Mock 外部依赖（API 调用、子组件等）

### 4. 图表组件测试
- Mock ECharts 组件
- 测试图表配置的生成
- 测试数据处理和转换
- 测试响应式设计

## 常用测试模式

### 1. Mock 外部依赖
```typescript
vi.mock('../api/hooks', () => ({
  fetchData: vi.fn()
}))
```

### 2. 异步操作测试
```typescript
await waitFor(() => {
  expect(screen.getByText('Expected Text')).toBeInTheDocument()
})
```

### 3. 用户交互测试
```typescript
const user = userEvent.setup()
await user.click(screen.getByRole('button'))
```

## 测试最佳实践

1. **描述性测试名称**: 测试名称应该清楚说明测试的功能
2. **AAA 模式**: Arrange（准备）、Act（执行）、Assert（断言）
3. **独立测试**: 每个测试应该独立运行，不依赖其他测试
4. **适当的 Mock**: 只 Mock 必要的外部依赖
5. **覆盖边界情况**: 测试正常情况和异常情况

## 故障排查

### 常见问题和解决方案

1. **window.matchMedia is not a function**
   - 在 `setup.ts` 中添加 matchMedia mock

2. **window.getComputedStyle 错误**
   - 在 `setup.ts` 中添加 getComputedStyle mock

3. **ResizeObserver 错误**
   - 在 `setup.ts` 中添加 ResizeObserver mock

4. **React state updates not wrapped in act(...)**
   - 使用 `waitFor` 或 `act` 包装状态更新

## 持续改进

- 定期检查测试覆盖率
- 添加集成测试
- 考虑端到端测试
- 优化测试性能
- 保持测试代码的可维护性