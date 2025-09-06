import { Typography } from "antd";
import { Link } from "react-router-dom";
import type { SignalRow } from "../api/types";
import SignalTags from "./SignalTags";

export interface InstrumentData {
  ts_code?: string;
  name?: string;
  inst_name?: string; // 兼容不同字段名
  category_id?: string;
  cat_name?: string;
  cat_sub?: string;
}

export interface InstrumentDisplayProps {
  /** 标的数据 */
  data: InstrumentData;
  /** 显示模式 */
  mode?: 'combined' | 'code-only' | 'name-only' | 'text-only';
  /** 是否显示链接 */
  showLink?: boolean;
  /** 信号数据（用于显示信号标签） */
  signals?: SignalRow[];
  /** 最大显示信号数量 */
  maxSignals?: number;
  /** 信号显示样式 */
  signalVariant?: 'default' | 'solid';
  /** 自定义样式 */
  style?: React.CSSProperties;
  /** 代码样式 */
  codeStyle?: React.CSSProperties;
  /** 名称样式 */
  nameStyle?: React.CSSProperties;
}

/**
 * 统一的标的信息显示组件
 */
export default function InstrumentDisplay({
  data,
  mode = 'combined',
  showLink = true,
  signals,
  maxSignals = 3,
  signalVariant = 'default',
  style,
  codeStyle,
  nameStyle,
}: InstrumentDisplayProps) {
  const { ts_code, name, inst_name, category_id } = data;
  
  // 优先使用 name，回退到 inst_name
  const displayName = name || inst_name;

  // 默认样式
  const defaultCodeStyle: React.CSSProperties = {
    fontWeight: "bold",
    display: "block",
    ...codeStyle,
  };

  const defaultNameStyle: React.CSSProperties = {
    color: "#667085",
    fontSize: "12px",
    ...nameStyle,
  };

  const containerStyle: React.CSSProperties = {
    ...style,
  };

  // 渲染代码部分
  const renderCode = () => {
    if (!ts_code) return null;

    const codeElement = (
      <span style={defaultCodeStyle}>
        {ts_code}
      </span>
    );

    return showLink ? (
      <Link to={`/instrument/${ts_code}`} style={defaultCodeStyle}>
        {ts_code}
      </Link>
    ) : codeElement;
  };

  // 渲染名称部分
  const renderName = () => {
    if (!displayName) return null;

    return (
      <Typography.Text type="secondary" style={defaultNameStyle}>
        {displayName}
      </Typography.Text>
    );
  };

  // 渲染类别信息
  const renderCategory = () => {
    if (!category_id) return null;

    return (
      <Typography.Text style={{ color: "#666" }}>
        类别 {category_id}
      </Typography.Text>
    );
  };

  // 渲染信号标签
  const renderSignals = () => {
    if (!signals || signals.length === 0) return null;

    return <SignalTags signals={signals} maxDisplay={maxSignals} variant={signalVariant} />;
  };

  // 根据模式渲染不同内容
  switch (mode) {
    case 'code-only':
      return <div style={containerStyle}>{renderCode()}</div>;
    
    case 'name-only':
      return <div style={containerStyle}>{renderName()}</div>;
    
    case 'text-only':
      if (ts_code) {
        return (
          <span style={containerStyle}>
            {ts_code}{displayName ? ` ${displayName}` : ''}
          </span>
        );
      }
      return <span style={containerStyle}>{displayName || renderCategory() || '-'}</span>;
    
    case 'combined':
    default:
      if (ts_code) {
        return (
          <div style={containerStyle}>
            {renderCode()}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              {renderName()}
              {renderSignals()}
            </div>
          </div>
        );
      }
      
      // 回退到类别显示
      return <div style={containerStyle}>{renderCategory() || '-'}</div>;
  }
}

/**
 * 生成标的下拉选项的工具函数
 */
export function createInstrumentOptions(instruments: InstrumentData[]) {
  return instruments.map((item) => ({
    value: item.ts_code || '',
    label: `${item.ts_code || ''}｜${item.name || item.inst_name || ''}${
      item.cat_name 
        ? `（${item.cat_name}${item.cat_sub ? `/${item.cat_sub}` : ''}）` 
        : ''
    }`,
  }));
}

/**
 * 获取标的的显示文本（用于纯文本场景）
 */
export function getInstrumentDisplayText(data: InstrumentData): string {
  const { ts_code, name, inst_name, category_id } = data;
  const displayName = name || inst_name;
  
  if (ts_code) {
    return displayName ? `${ts_code} ${displayName}` : ts_code;
  }
  
  if (category_id) {
    return `类别 ${category_id}`;
  }
  
  return displayName || '-';
}