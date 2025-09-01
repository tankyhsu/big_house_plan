import { Space, Button, DatePicker, Input } from "antd";
import dayjs, { Dayjs } from "dayjs";

type Props = {
  range: [Dayjs, Dayjs];
  onRangeChange: (r: [Dayjs, Dayjs]) => void;
  maInput: string;
  onMaInputChange: (v: string) => void;
  onApplyMaInput: () => void;
  onOpenFullscreen?: () => void;
};

export default function CandleToolbar({ range, onRangeChange, maInput, onMaInputChange, onApplyMaInput, onOpenFullscreen }: Props) {
  return (
    <Space>
      <Button size="small" onClick={() => onRangeChange([dayjs().subtract(3, "month"), dayjs()])}>近3月</Button>
      <Button size="small" onClick={() => onRangeChange([dayjs().subtract(6, "month"), dayjs()])}>近6月</Button>
      <Button size="small" onClick={() => onRangeChange([dayjs().subtract(12, "month"), dayjs()])}>近1年</Button>
      <Button size="small" onClick={onOpenFullscreen}>全屏</Button>
      <span>MA</span>
      <Input
        size="small"
        style={{ width: 120 }}
        value={maInput}
        onChange={e => onMaInputChange(e.target.value)}
        onPressEnter={onApplyMaInput}
        onBlur={onApplyMaInput}
        placeholder="20,30,60"
      />
      <DatePicker.RangePicker
        value={range}
        allowClear={false}
        onChange={(v) => {
          if (!v || !v[0] || !v[1]) return;
          onRangeChange([v[0], v[1]]);
        }}
      />
    </Space>
  );
}

