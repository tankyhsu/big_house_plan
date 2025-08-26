import { useEffect, useState } from "react";
import { Card, Form, InputNumber, Button, Space, message, Switch, Typography, Divider } from "antd";
import { fetchSettings, updateSettings } from "../api/hooks";

export default function SettingsPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [recalc, setRecalc] = useState(true);

  useEffect(() => {
    fetchSettings().then((cfg) => {
      form.setFieldsValue({
        unit_amount: cfg.unit_amount ?? 3000,
        stop_gain_pct: (cfg.stop_gain_pct ?? 0.3) * 100,     // 百分数显示
        overweight_band: (cfg.overweight_band ?? 0.2) * 100, // 百分数显示
      });
    });
  }, []);

  const onSave = async () => {
    try {
      const vals = await form.validateFields();
      setLoading(true);
      // 转回小数
      const updates: Record<string, any> = {
        unit_amount: Number(vals.unit_amount),
        stop_gain_pct: Number(vals.stop_gain_pct) / 100,
        overweight_band: Number(vals.overweight_band) / 100,
      };
      await updateSettings(updates, recalc);
      message.success(`已保存。${recalc ? "已按新份额重算今日快照。" : ""}`);
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.message || "保存失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="系统设置" size="small" bodyStyle={{ paddingBottom: 8 }}>
      <Form form={form} layout="vertical" style={{ maxWidth: 520 }}>
        <Form.Item
          label="一份资金（元）"
          name="unit_amount"
          rules={[
            { required: true, message: "请输入每份资金的金额" },
            { type: "number", min: 1, message: "必须大于 0" },
          ]}
        >
          <InputNumber controls={false} precision={0} style={{ width: 240 }} placeholder="例如 3000" />
        </Form.Item>

        <Divider style={{ margin: "8px 0" }} />

        <Form.Item
          label="止盈阈值（%）"
          name="stop_gain_pct"
          tooltip="当标的收益率 ≥ 此百分比时触发止盈信号"
          rules={[
            { required: true, message: "请输入止盈阈值" },
            { type: "number", min: 0, message: "不能小于 0" },
          ]}
        >
          <InputNumber controls={false} precision={2} style={{ width: 240 }} placeholder="例如 30 表示 +30%" />
        </Form.Item>

        <Form.Item
          label="配置偏离带宽（±%）"
          name="overweight_band"
          tooltip="实际份数相对目标份数的允许偏离范围，超出将提示再平衡"
          rules={[
            { required: true, message: "请输入带宽百分比" },
            { type: "number", min: 0, message: "不能小于 0" },
          ]}
        >
          <InputNumber controls={false} precision={2} style={{ width: 240 }} placeholder="例如 20 表示 ±20%" />
        </Form.Item>

        <Space align="center" style={{ marginTop: 8, marginBottom: 12 }}>
          <Switch checked={recalc} onChange={setRecalc} />
          <Typography.Text>保存后重算今日快照</Typography.Text>
        </Space>

        {/* 按钮放最底部、单列、占满宽度 */}
        <Form.Item style={{ marginTop: 16 }}>
          <Button type="primary" onClick={onSave} loading={loading} block>
            保存设置
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );
}