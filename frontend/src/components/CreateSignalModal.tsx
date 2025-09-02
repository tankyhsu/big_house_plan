import { useState, useEffect } from "react";
import { Modal, Form, Input, Select, DatePicker, message, AutoComplete } from "antd";
import dayjs, { Dayjs } from "dayjs";
import { createSignal, fetchInstruments, fetchCategories, type SignalCreatePayload } from "../api/hooks";
import type { InstrumentLite, CategoryLite, SignalLevel, SignalType } from "../api/types";
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
}

export default function CreateSignalModal({ open, onClose, onSuccess }: CreateSignalModalProps) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [instruments, setInstruments] = useState<InstrumentLite[]>([]);
  const [categories, setCategories] = useState<CategoryLite[]>([]);
  const [targetType, setTargetType] = useState<'instrument' | 'category'>('instrument');

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
      };

      if (targetType === 'instrument') {
        payload.ts_code = values.ts_code;
      } else {
        payload.category_id = values.category_id;
      }

      await createSignal(payload);
      message.success("信号创建成功！");
      form.resetFields();
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
          label="信号目标"
          name="target_type"
          initialValue="instrument"
        >
          <Select
            value={targetType}
            onChange={setTargetType}
            options={[
              { value: 'instrument', label: '特定标的' },
              { value: 'category', label: '整个类别' },
            ]}
          />
        </Form.Item>

        {targetType === 'instrument' ? (
          <Form.Item
            label="选择标的"
            name="ts_code"
            rules={[{ required: true, message: "请选择标的" }]}
          >
            <AutoComplete
              options={instrumentOptions}
              placeholder="输入标的代码或名称"
              showSearch
              filterOption={(input, option) =>
                option?.label?.toLowerCase().includes(input.toLowerCase()) ?? false
              }
            />
          </Form.Item>
        ) : (
          <Form.Item
            label="选择类别"
            name="category_id"
            rules={[{ required: true, message: "请选择类别" }]}
          >
            <Select
              options={categoryOptions}
              placeholder="选择类别"
              showSearch
              filterOption={(input, option) =>
                option?.label?.toLowerCase().includes(input.toLowerCase()) ?? false
              }
            />
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