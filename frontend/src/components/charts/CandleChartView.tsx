import ReactECharts from "echarts-for-react";
import { Modal } from "antd";

type Props = {
  option: unknown;
  height: number;
  title: string;
  fullscreen: boolean;
  onOpen: () => void;
  onClose: () => void;
};

export default function CandleChartView({ option, height, title, fullscreen, onOpen, onClose }: Props) {
  return (
    <>
      <div onClick={onOpen}>
        <ReactECharts 
          notMerge 
          lazyUpdate 
          option={option} 
          style={{ height, cursor: 'zoom-in' as any }}
        />
      </div>
      <Modal
        title={`${title} - 全屏`}
        open={fullscreen}
        onCancel={onClose}
        footer={null}
        width={"100vw"}
        style={{ top: 8 }}
        styles={{ body: { padding: 8 } }}
      >
        <ReactECharts 
          notMerge 
          lazyUpdate 
          option={option} 
          style={{ height }}
        />
      </Modal>
    </>
  );
}

