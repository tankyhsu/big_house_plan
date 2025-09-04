import { useState, useEffect } from "react";
import { Modal, Form, Input, Select, DatePicker, message } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { createSignal, fetchInstruments, fetchCategories, type SignalCreatePayload } from "../api/hooks";
import type { InstrumentLite, CategoryLite, SignalLevel, SignalType, SignalScopeType } from "../api/types";
import { SIGNAL_CONFIG, LEVEL_CONFIG } from "../utils/signalConfig";

interface CreateSignalModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface FormValues {
  trade_date: Dayjs;
  level: SignalLevel;
  type: SignalType;
  message: string;
  ts_code?: string;
  category_id?: number;
  scope_type: SignalScopeType;
  scope_data?: string[];
}

export default function CreateSignalModal({ open, onClose, onSuccess }: CreateSignalModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [instruments, setInstruments] = useState<InstrumentLite[]>([]);
  const [categories, setCategories] = useState<CategoryLite[]>([]);
  const [scopeType, setScopeType] = useState<SignalScopeType>('INSTRUMENT');

  // 加载标的和类别数据
  useEffect(() => {
    if (open) {
      Promise.all([fetchInstruments(), fetchCategories()])
        .then(([instData, catData]) => {
          setInstruments(instData);
          setCategories(catData);
        })
        .catch(console.error);
    }
  }, [open]);

  const handleSubmit = async (values: FormValues) => {
    setLoading(true);
    try {
      const payload: SignalCreatePayload = {
        trade_date: values.trade_date.format("YYYY-MM-DD"),
        level: values.level,
        type: values.type,
        message: values.message,
        scope_type: values.scope_type,
        // ALL_INSTRUMENTS和ALL_CATEGORIES类型不需要scope_data，动态获取
        scope_data: values.scope_type === 'ALL_INSTRUMENTS' || values.scope_type === 'ALL_CATEGORIES' 
          ? undefined 
          : values.scope_data,
      };

      // 兼容性处理：为了保持旧API兼容性
      if (values.scope_type === 'INSTRUMENT' && values.scope_data?.length === 1) {
        payload.ts_code = values.scope_data[0];
      } else if (values.scope_type === 'CATEGORY' && values.scope_data?.length === 1) {
        payload.category_id = parseInt(values.scope_data[0]);
      }

      await createSignal(payload);
      message.success("信号创建成功！");
      form.resetFields();
      setScopeType('INSTRUMENT');
      onSuccess();
      onClose();
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error && 
        error.response && typeof error.response === 'object' && 'data' in error.response &&
        error.response.data && typeof error.response.data === 'object' && 'detail' in error.response.data
        ? error.response.data.detail
        : error && typeof error === 'object' && 'message' in error 
        ? error.message 
        : "创建失败";
      message.error(String(errorMessage));
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    setScopeType('INSTRUMENT');
    onClose();
  };

  const instrumentOptions = instruments.map(inst => ({
    value: inst.ts_code,
    label: `${inst.ts_code} - ${inst.name}`,
  }));

  const categoryOptions = categories.map(cat => ({
    value: cat.id,
    label: `${cat.name}${cat.sub_name ? ` / ${cat.sub_name}` : ''}`,
  }));

  return (
    <Modal
      title="创建手动信号"
      open={open}
      onOk={form.submit}
      onCancel={handleCancel}
      confirmLoading={loading}
      width={600}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          trade_date: dayjs(),
          level: 'INFO',
          type: 'BULLISH',
          scope_type: 'INSTRUMENT',
        }}
      >
        <Form.Item
          label="信号日期"
          name="trade_date"
          rules={[{ required: true, message: "请选择信号日期" }]}
        >
          <DatePicker style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          label="信号范围"
          name="scope_type"
          rules={[{ required: true, message: "请选择信号范围" }]}
        >
          <Select
            value={scopeType}
            onChange={setScopeType}
            options={[
              { value: 'INSTRUMENT', label: '单个标的' },
              { value: 'MULTI_INSTRUMENT', label: '多个标的' },
              { value: 'ALL_INSTRUMENTS', label: '所有标的' },
              { value: 'CATEGORY', label: '单个类别' },
              { value: 'MULTI_CATEGORY', label: '多个类别' },
              { value: 'ALL_CATEGORIES', label: '所有类别' },
            ]}
          />
        </Form.Item>

        {(scopeType === 'INSTRUMENT' || scopeType === 'MULTI_INSTRUMENT') && (
          <Form.Item
            label={scopeType === 'INSTRUMENT' ? "选择标的" : "选择多个标的"}
            name="scope_data"
            rules={[{ required: true, message: "请选择标的" }]}
          >
            <Select
              mode={scopeType === 'MULTI_INSTRUMENT' ? 'multiple' : undefined}
              options={instrumentOptions}
              placeholder={scopeType === 'INSTRUMENT' ? "选择一个标的" : "选择多个标的"}
              showSearch
              filterOption={(input, option) =>
                option?.label?.toLowerCase().includes(input.toLowerCase()) ?? false
              }
            />
          </Form.Item>
        )}

        {(scopeType === 'CATEGORY' || scopeType === 'MULTI_CATEGORY') && (
          <Form.Item
            label={scopeType === 'CATEGORY' ? "选择类别" : "选择多个类别"}
            name="scope_data"
            rules={[{ required: true, message: "请选择类别" }]}
          >
            <Select
              mode={scopeType === 'MULTI_CATEGORY' ? 'multiple' : undefined}
              options={categoryOptions.map(cat => ({
                value: cat.value.toString(),
                label: cat.label,
              }))}
              placeholder={scopeType === 'CATEGORY' ? "选择一个类别" : "选择多个类别"}
              showSearch
              filterOption={(input, option) =>
                option?.label?.toLowerCase().includes(input.toLowerCase()) ?? false
              }
            />
          </Form.Item>
        )}

        {scopeType === 'ALL_INSTRUMENTS' && (
          <Form.Item>
            <div style={{ padding: '12px', backgroundColor: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '6px' }}>
              <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>此信号将应用于所有激活的标的</div>
              <div style={{ fontSize: '12px', color: '#666' }}>
                包括当前所有激活标的以及后续新增的激活标的。<br/>
                信号作为客观市场事实，会动态覆盖所有符合条件的标的。
              </div>
            </div>
          </Form.Item>
        )}

        {scopeType === 'ALL_CATEGORIES' && (
          <Form.Item>
            <div style={{ padding: '12px', backgroundColor: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '6px' }}>
              <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>此信号将应用于所有类别</div>
              <div style={{ fontSize: '12px', color: '#666' }}>
                包括当前所有类别以及后续新增的类别。<br/>
                信号作为客观市场事实，会动态覆盖所有符合条件的类别。
              </div>
            </div>
          </Form.Item>
        )}

        <Form.Item
          label="信号类型"
          name="type"
          rules={[{ required: true, message: "请选择信号类型" }]}
        >
          <Select
            options={Object.entries(SIGNAL_CONFIG).map(([type, config]) => ({
              value: type,
              label: config.label,
            }))}
            placeholder="选择信号类型"
          />
        </Form.Item>

        <Form.Item
          label="信号级别"
          name="level"
          rules={[{ required: true, message: "请选择信号级别" }]}
        >
          <Select
            options={Object.entries(LEVEL_CONFIG).map(([level, config]) => ({
              value: level,
              label: config.label,
            }))}
            placeholder="选择信号级别"
          />
        </Form.Item>

        <Form.Item
          label="信号描述"
          name="message"
          rules={[
            { required: true, message: "请输入信号描述" },
            { max: 500, message: "描述不能超过500字符" }
          ]}
        >
          <Input.TextArea
            rows={4}
            placeholder="描述政策变化、市场环境变化或其他重要信息..."
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}