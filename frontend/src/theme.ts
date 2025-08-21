import type { ThemeConfig } from "antd";

const theme: ThemeConfig = {
  token: {
    borderRadius: 10,
    colorPrimary: "#1677ff",
    colorInfo: "#1677ff",
  },
  components: {
    Card: { paddingLG: 16 },
    Table: { cellPaddingBlock: 10, headerColor: "#667085" },
  },
};

export default theme;