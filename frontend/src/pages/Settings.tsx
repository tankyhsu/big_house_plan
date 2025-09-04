import { useEffect, useState, useRef } from "react";
import { Card, Form, InputNumber, Button, message, Divider, Upload, Space, Row, Col, Modal } from "antd";
import { DownloadOutlined, UploadOutlined, ExclamationCircleOutlined } from "@ant-design/icons";
import { fetchSettings, updateSettings, downloadBackup, uploadRestore } from "../api/hooks";

export default function SettingsPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [backupLoading, setBackupLoading] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);

  useEffect(() => {
    fetchSettings().then((cfg) => {
      form.setFieldsValue({
        unit_amount: cfg.unit_amount ?? 3000,
        stop_gain_pct: (cfg.stop_gain_pct ?? 0.3) * 100,     // 百分数显示
        stop_loss_pct: (cfg.stop_loss_pct ?? 0.15) * 100,    // 百分数显示
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
        stop_loss_pct: Number(vals.stop_loss_pct) / 100,
        overweight_band: Number(vals.overweight_band) / 100,
      };
      await updateSettings(updates);
      message.success("设置已保存，份数显示将自动更新。");
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.message || "保存失败");
    } finally {
      setLoading(false);
    }
  };

  const onBackup = async () => {
    try {
      setBackupLoading(true);
      await downloadBackup();
      message.success("数据备份下载成功");
    } catch (e: any) {
      message.error(e?.message || "备份失败");
    } finally {
      setBackupLoading(false);
    }
  };

  const parseBackupInfo = async (file: File): Promise<{ timestamp?: string; tables?: any; error?: string }> => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const content = e.target?.result as string;
          const data = JSON.parse(content);
          resolve(data);
        } catch (error) {
          resolve({ error: "无法解析备份文件" });
        }
      };
      reader.readAsText(file);
    });
  };

  const onRestore = async (file: File) => {
    try {
      // 先解析文件信息
      const backupInfo = await parseBackupInfo(file);
      
      if (backupInfo.error) {
        message.error(backupInfo.error);
        return;
      }

      // 优先使用中文格式的备份时间，其次使用ISO时间戳
      const backupDate = backupInfo.backup_date || 
        (backupInfo.timestamp ? 
          new Date(backupInfo.timestamp).toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          }) : '未知时间');

      const tableCount = backupInfo.tables ? Object.keys(backupInfo.tables).length : 0;
      const summary = backupInfo.summary || {};
      
      // 显示确认对话框
      Modal.confirm({
        title: '确认恢复数据',
        width: 520,
        icon: <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />,
        content: (
          <div style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 16 }}>
              <p><strong>📅 备份时间：</strong>{backupDate}</p>
              <p><strong>📊 版本信息：</strong>v{backupInfo.version || '未知'}</p>
              <p><strong>📁 数据表数：</strong>{tableCount} 个</p>
            </div>
            
            {Object.keys(summary).length > 0 && (
              <div style={{ 
                marginBottom: 16, 
                padding: '12px', 
                backgroundColor: '#f6f8fa', 
                borderRadius: '6px',
                fontSize: '13px'
              }}>
                <strong>📋 数据概览：</strong><br />
                {Object.entries(summary).map(([table, count]) => (
                  <span key={table} style={{ marginRight: 16 }}>
                    {table}: {count}条
                  </span>
                ))}
              </div>
            )}
            
            <div style={{ 
              color: '#ff4d4f', 
              padding: '12px', 
              backgroundColor: '#fff2f0', 
              border: '1px solid #ffccc7',
              borderRadius: '6px'
            }}>
              <strong>⚠️ 重要提醒：</strong><br />
              此操作将完全覆盖当前所有业务数据，且无法撤销！<br />
              请确保您了解此备份的内容和时间。
            </div>
          </div>
        ),
        okText: '确认恢复',
        okType: 'danger',
        cancelText: '取消',
        onOk: async () => {
          try {
            setRestoreLoading(true);
            const result = await uploadRestore(file);
            message.success(result.message || "数据恢复成功");
            // 刷新设置数据
            setTimeout(() => window.location.reload(), 1000);
          } catch (e: any) {
            message.error(e?.response?.data?.detail || e?.message || "恢复失败");
          } finally {
            setRestoreLoading(false);
          }
        }
      });
    } catch (e: any) {
      message.error("文件处理失败");
    }
  };

  return (
    <div style={{ padding: '0 24px' }}>
      <Row gutter={24}>
        <Col xs={24} lg={12}>
          <Card title="系统配置" size="small" style={{ marginBottom: 16 }}>
            <Form form={form} layout="vertical">
              <Form.Item
                label="一份资金（元）"
                name="unit_amount"
                rules={[
                  { required: true, message: "请输入每份资金的金额" },
                  { type: "number", min: 1, message: "必须大于 0" },
                ]}
              >
                <InputNumber 
                  controls={false} 
                  precision={0} 
                  style={{ width: '100%' }} 
                  placeholder="例如 3000" 
                />
              </Form.Item>

              <Form.Item
                label="止盈阈值（%）"
                name="stop_gain_pct"
                tooltip="当标的收益率 ≥ 此百分比时触发止盈信号"
                rules={[
                  { required: true, message: "请输入止盈阈值" },
                  { type: "number", min: 0, message: "不能小于 0" },
                ]}
              >
                <InputNumber 
                  controls={false} 
                  precision={2} 
                  style={{ width: '100%' }} 
                  placeholder="例如 30 表示 +30%" 
                />
              </Form.Item>

              <Form.Item
                label="止损阈值（%）"
                name="stop_loss_pct"
                tooltip="当标的收益率 ≤ 此百分比的负值时触发止损信号"
                rules={[
                  { required: true, message: "请输入止损阈值" },
                  { type: "number", min: 0, message: "不能小于 0" },
                ]}
              >
                <InputNumber 
                  controls={false} 
                  precision={2} 
                  style={{ width: '100%' }} 
                  placeholder="例如 15 表示 -15%" 
                />
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
                <InputNumber 
                  controls={false} 
                  precision={2} 
                  style={{ width: '100%' }} 
                  placeholder="例如 20 表示 ±20%" 
                />
              </Form.Item>

              <Form.Item style={{ marginTop: 24 }}>
                <Button type="primary" onClick={onSave} loading={loading} block size="large">
                  保存设置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="数据管理" size="small" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              <div>
                <Button 
                  icon={<DownloadOutlined />}
                  onClick={onBackup}
                  loading={backupLoading}
                  block
                  size="large"
                  type="primary"
                  ghost
                >
                  备份数据
                </Button>
                <div style={{ fontSize: '12px', color: '#666', marginTop: 8, textAlign: 'center' }}>
                  下载包含所有业务数据的JSON文件
                </div>
              </div>
              
              <div>
                <Upload
                  accept=".json"
                  beforeUpload={(file) => {
                    onRestore(file);
                    return false; // 阻止默认上传
                  }}
                  showUploadList={false}
                >
                  <Button 
                    icon={<UploadOutlined />}
                    loading={restoreLoading}
                    block
                    danger
                    size="large"
                  >
                    恢复数据
                  </Button>
                </Upload>
                <div style={{ fontSize: '12px', color: '#ff4d4f', marginTop: 8, textAlign: 'center' }}>
                  ⚠️ 恢复操作会覆盖所有现有数据
                </div>
              </div>

              <Divider style={{ margin: '16px 0' }} />
              
              <div style={{ 
                padding: '12px', 
                backgroundColor: '#f6f8fa', 
                borderRadius: '6px',
                fontSize: '12px',
                color: '#666'
              }}>
                <strong>备份说明：</strong><br />
                • 包含配置、分类、标的、交易、价格等业务数据<br />
                • 不包含操作日志<br />
                • 建议定期备份以防数据丢失
              </div>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
