import { ConfigProvider, Layout, Menu } from "antd";
import zhCN from "antd/locale/zh_CN";
import theme from "./theme";
import Dashboard from "./pages/Dashboard";
import PositionEditor from "./pages/PositionEditor";
import TxnPage from "./pages/Txn";
import { Link, Route, Routes, useLocation } from "react-router-dom";

const { Header, Content, Footer } = Layout;

function TopNav() {
  const location = useLocation();
  const selectedKeys =
    location.pathname.startsWith("/positions") ? ["positions"] :
    location.pathname.startsWith("/txn") ? ["txn"] :
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
          { key: "positions", label: <Link to="/positions">持仓编辑</Link> },
          { key: "txn", label: <Link to="/txn">交易</Link> },
        ]}
        style={{ flex: 1, minWidth: 0 }}
      />
    </Header>
  );
}

export default function App() {
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <Layout style={{ minHeight: "100vh", background: "#f5f7fb" }}>
        <TopNav />
        <Content style={{ padding: 16, maxWidth: 1200, margin: "0 auto", width: "100%" }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/positions" element={<PositionEditor />} />
            <Route path="/txn" element={<TxnPage />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </Content>
        <Footer style={{ textAlign: "center", color: "#98A2B3" }}>
          © {new Date().getFullYear()} Your Portfolio
        </Footer>
      </Layout>
    </ConfigProvider>
  );
}