import { useEffect, useState, useRef } from "react";
import { Card, Form, InputNumber, Button, message, Divider, Upload, Space, Modal, Input, Table, Tabs, Select, notification } from "antd";
import { DownloadOutlined, UploadOutlined, ExclamationCircleOutlined } from "@ant-design/icons";
import { fetchSettings, updateSettings, downloadBackup, uploadRestore, fetchCategories, createCategory, updateCategory, updateCategoriesBulk } from "../api/hooks";
import type { CategoryLite } from "../api/types";

export default function SettingsPage() {
  const MAX_UNITS = 150;
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [backupLoading, setBackupLoading] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [catLoading, setCatLoading] = useState(false);
  const [categories, setCategories] = useState<CategoryLite[]>([]);
  const [catForm] = Form.useForm();
  const [editCache, setEditCache] = useState<Record<number, { sub_name?: string; target_units?: number }>>({});
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  // 计算“实时有效”的分类列表（考虑未保存的编辑）
  const effectiveCategories = () => {
    return categories.map((c) => {
      const pending = editCache[c.id] || {};
      const tu = typeof pending.target_units === 'number' && !Number.isNaN(pending.target_units)
        ? pending.target_units!
        : c.target_units;
      return { ...c, sub_name: pending.sub_name ?? c.sub_name, target_units: tu };
    });
  };

  const totalUnits = () => effectiveCategories().reduce((sum, c) => sum + Number(c.target_units || 0), 0);
  const remainingUnits = () => Math.max(0, MAX_UNITS - totalUnits());
  const overCap = () => totalUnits() > MAX_UNITS;

  const groupStats = () => {
    const list = effectiveCategories();
    const total = totalUnits();
    const map = new Map<string, number>();
    for (const c of list) {
      const key = c.name || '未分组';
      map.set(key, (map.get(key) || 0) + Number(c.target_units || 0));
    }
    const out = Array.from(map.entries()).map(([name, units]) => ({ name, units, pct: total > 0 ? (units / total) * 100 : 0 }));
    out.sort((a, b) => b.units - a.units);
    return out;
  };

  useEffect(() => {
    fetchSettings().then((cfg) => {
      form.setFieldsValue({
        unit_amount: cfg.unit_amount ?? 3000,
        stop_gain_pct: (cfg.stop_gain_pct ?? 0.3) * 100,     // 百分数显示
        stop_loss_pct: (cfg.stop_loss_pct ?? 0.15) * 100,    // 百分数显示
        overweight_band: (cfg.overweight_band ?? 0.2) * 100, // 百分数显示
      });
    });
    // 加载类别列表
    reloadCategories();
  }, []);

  const reloadCategories = async () => {
    setCatLoading(true);
    try {
      const list = await fetchCategories();
      setCategories(list);
      setEditCache({});
    } finally {
      setCatLoading(false);
    }
  };

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

  const onCreateCategory = async () => {
    try {
      const vals = await catForm.validateFields();
      const addUnits = Number(vals.target_units);
      const newTotal = totalUnits() + (Number.isFinite(addUnits) ? addUnits : 0);
      if (newTotal > MAX_UNITS) {
        message.error(`总目标份数不可超过 ${MAX_UNITS} 份，当前保存后将达到 ${newTotal.toFixed(2)} 份`);
        return;
      }
      const res = await createCategory({ name: vals.name, sub_name: vals.sub_name || "", target_units: addUnits });
      message.success("新增类别成功");
      catForm.resetFields();
      await reloadCategories();
      if (res?.id) {
        const id = Number(res.id);
        setSelectedRowKeys([id]);
        setTimeout(() => {
          const rowEl = document.querySelector(`[data-row-key="${id}"]`);
          if (rowEl && 'scrollIntoView' in rowEl) {
            (rowEl as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 100);
      }
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.message || "新增失败");
    }
  };

  const onSaveCategory = async (row: CategoryLite) => {
    const pending = editCache[row.id] || {};
    if (pending.sub_name === undefined && pending.target_units === undefined) {
      message.info("没有可保存的修改");
      return;
    }
    try {
      // 实时总份数校验（考虑当前未保存编辑）
      if (overCap()) {
        message.error(`总目标份数不可超过 ${MAX_UNITS} 份（当前为 ${totalUnits().toFixed(2)} 份）`);
        return;
      }
      await updateCategory({ id: row.id, ...pending });
      message.success("保存成功");
      reloadCategories();
    } catch (e: any) {
      message.error(e?.message || "保存失败");
    }
  };

  const onSaveAll = async () => {
    try {
      if (overCap()) {
        message.error(`总目标份数不可超过 ${MAX_UNITS} 份（当前为 ${totalUnits().toFixed(2)} 份）`);
        return;
      }
      // 仅发送有变化的字段
      const items: { id: number; sub_name?: string; target_units?: number }[] = [];
      for (const c of categories) {
        const p = editCache[c.id] || {};
        const changes: any = { id: c.id };
        let changed = false;
        if (p.sub_name !== undefined && p.sub_name !== c.sub_name) {
          changes.sub_name = p.sub_name; changed = true;
        }
        if (p.target_units !== undefined && Number(p.target_units) !== Number(c.target_units)) {
          changes.target_units = Number(p.target_units); changed = true;
        }
        if (changed) items.push(changes);
      }
      if (items.length === 0) {
        message.info("没有需要保存的修改");
        return;
      }
      const res = await updateCategoriesBulk(items);
      const total = Number(res?.total ?? totalUnits());
      if (res.auto_fill && res.auto_fill > 0) {
        const cashName = res.cash_category?.name || '现金';
        const cashSub = res.cash_category?.sub_name ? ` - ${res.cash_category?.sub_name}` : '';
        notification.success({
          message: "保存成功",
          description: `剩余 ${(res.auto_fill as number).toFixed?.(2) ?? res.auto_fill} 份已自动分配至 ${cashName}${cashSub}；当前总份数 ${total.toFixed(2)}/150`,
          placement: "topRight",
          duration: 2.5,
        });
      } else {
        notification.success({
          message: "保存成功",
          description: `当前总份数 ${total.toFixed(2)}/150`,
          placement: "topRight",
          duration: 2.5,
        });
      }
      setEditCache({});
      reloadCategories();
    } catch (e: any) {
      message.error(e?.message || "保存失败");
    }
  };

  const columns = [
    {
      title: "大类",
      dataIndex: "name",
      key: "name",
      render: (text: string) => <span style={{ color: '#888' }}>{text}</span>,
    },
    {
      title: "二级分类",
      dataIndex: "sub_name",
      key: "sub_name",
      render: (_: any, record: CategoryLite) => (
        <Input
          defaultValue={record.sub_name}
          onChange={(e) => setEditCache((prev) => ({ ...prev, [record.id]: { ...prev[record.id], sub_name: e.target.value } }))}
          placeholder="可编辑"
        />
      ),
    },
    {
      title: "目标份数",
      dataIndex: "target_units",
      key: "target_units",
      width: 160,
      render: (_: any, record: CategoryLite) => (
        <InputNumber
          defaultValue={record.target_units}
          controls={false}
          precision={2}
          style={{ width: '100%' }}
          onChange={(val) => setEditCache((prev) => ({ ...prev, [record.id]: { ...prev[record.id], target_units: Number(val) } }))}
        />
      ),
    },
    {
      title: "操作",
      key: "actions",
      width: 120,
      render: (_: any, record: CategoryLite) => (
        <Button type="link" onClick={() => onSaveCategory(record)}>保存</Button>
      ),
    },
  ];

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
      <Tabs
        defaultActiveKey="system"
        items={[
          {
            key: 'system',
            label: '系统配置',
            children: (
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
            ),
          },
          {
            key: 'category',
            label: '投资类别管理',
            children: (
              <Card title="投资类别管理" size="small" style={{ marginBottom: 16 }}
                    extra={<Button type="primary" onClick={onSaveAll}>保存全部</Button>}>
                {/* 新增置顶：仅允许选择已有大类 */}
                <Form form={catForm} layout="inline" style={{ marginBottom: 12 }}>
                  <Form.Item name="name" label="大类" rules={[{ required: true, message: '请选择大类' }]}>
                    <Select
                      placeholder="请选择大类"
                      style={{ width: 200 }}
                      options={Array.from(new Set((categories || []).map(c => c.name).filter(Boolean))).map(n => ({ label: n as string, value: n as string }))}
                    />
                  </Form.Item>
                  <Form.Item name="sub_name" label="二级分类">
                    <Input placeholder="如：A股ETF" style={{ width: 200 }} />
                  </Form.Item>
                  <Form.Item name="target_units" label="目标份数" rules={[{ required: true, message: '请输入份数' }]}>
                    <InputNumber controls={false} precision={2} style={{ width: 160 }} />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" onClick={onCreateCategory} disabled={Array.from(new Set((categories || []).map(c => c.name).filter(Boolean))).length === 0}>新增类别</Button>
                  </Form.Item>
                </Form>

                <div style={{ marginBottom: 12, fontSize: 12, color: '#666' }}>
                  <div style={{ marginBottom: 6 }}>
                    大类不可修改，仅可编辑二级分类名称与目标份数。
                  </div>
                  <div style={{
                    padding: '8px 12px',
                    borderRadius: 6,
                    border: `1px solid ${overCap() ? '#ffccc7' : '#d9d9d9'}`,
                    background: overCap() ? '#fff2f0' : '#fafafa',
                    color: overCap() ? '#cf1322' : '#595959'
                  }}>
                    <strong>总目标份数：</strong>
                    {totalUnits().toFixed(2)} / {MAX_UNITS}（剩余 {remainingUnits().toFixed(2)}）
                  </div>
                  <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
                    按大类统计：
                    {groupStats().map((g) => (
                      <span key={g.name} style={{ marginRight: 12 }}>
                        {g.name}: {g.units.toFixed(2)}份（{g.pct.toFixed(1)}%）
                      </span>
                    ))}
                  </div>
                </div>
                <Table
                  size="small"
                  rowKey="id"
                  loading={catLoading}
                  columns={columns.filter(col => col.key !== 'actions') as any}
                  dataSource={categories}
                  rowSelection={{ type: 'radio', selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys) }}
                  pagination={false}
                />
              </Card>
            ),
          },
          {
            key: 'data',
            label: '数据管理',
            children: (
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
            ),
          },
        ]}
      />
    </div>
  );
}
