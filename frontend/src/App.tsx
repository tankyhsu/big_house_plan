import { ConfigProvider, Layout, Menu, App as AntdApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import theme from "./theme";
import Dashboard from "./pages/Dashboard";
import PositionEditor from "./pages/PositionEditor";
import InstrumentDetail from "./pages/InstrumentDetail";
import TxnPage from "./pages/Txn";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import SettingsPage from "./pages/Settings";
import ReviewPage from "./pages/Review";
import SignalsPage from "./pages/Signals";
import WatchlistPage from "./pages/Watchlist";
import { SettingOutlined, AlertOutlined } from "@ant-design/icons";

const { Header, Content, Footer } = Layout;

function TopNav() {
  const location = useLocation();
  const selectedKeys =
    (location.pathname.startsWith("/positions") || location.pathname.startsWith("/instrument")) ? ["positions"] :
    location.pathname.startsWith("/watchlist") ? ["watchlist"] :
    location.pathname.startsWith("/txn") ? ["txn"] :
    location.pathname.startsWith("/review") ? ["review"] :
    location.pathname.startsWith("/signals") ? ["signals"] :
    location.pathname.startsWith("/settings") ? ["settings"] :
    ["dashboard"];

  return (
    <Header style={{ display: "flex", alignItems: "center", paddingInline: 16 }}>
      <div style={{ color: "#fff", fontWeight: 700, fontSize: 16, marginRight: 24 }}>Portfolio UI</div>
      <Menu
        mode="horizontal"
        theme="dark"
        selectedKeys={selectedKeys}
        items={[
          { key: "dashboard", label: <Link to="/">Dashboard</Link> },
          { key: "review", label: <Link to="/review">复盘分析</Link> },
          { key: "signals", icon: <AlertOutlined />, label: <Link to="/signals">交易信号</Link> },
          { key: "positions", label: <Link to="/positions">持仓管理</Link> },
          { key: "watchlist", label: <Link to="/watchlist">自选关注</Link> },
          { key: "txn", label: <Link to="/txn">交易记录</Link> },
          { key: "settings", icon: <SettingOutlined />, label:  <Link to="/settings">系统设置</Link> }
        ]}
        style={{ flex: 1, minWidth: 0 }}
      />
    </Header>
  );
}

export default function App() {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntdApp>
        <Layout style={{ minHeight: "100vh", background: "#f5f7fb" }}>
          <TopNav />
          <Content style={{ padding: 16, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/review" element={<ReviewPage />} />
              <Route path="/signals" element={<SignalsPage />} />
              <Route path="/positions" element={<PositionEditor />} />
              <Route path="/instrument/:ts_code" element={<InstrumentDetail />} />
              <Route path="/watchlist" element={<WatchlistPage />} />
              <Route path="/txn" element={<TxnPage />} />
              <Route path="/settings" element={<SettingsPage />} />  
              <Route path="*" element={<Dashboard />} />
            </Routes>
          </Content>
          <Footer style={{ textAlign: "center", color: "#98A2B3" }}>
            © {new Date().getFullYear()} Your Portfolio
          </Footer>
        </Layout>
      </AntdApp>
    </ConfigProvider>
  );
}
