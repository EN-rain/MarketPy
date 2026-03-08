export type BlockCategory = 'signal' | 'indicator' | 'operator' | 'action';

export interface PortDefinition {
  id: string;
  kind: 'input' | 'output';
  dataType: 'number' | 'boolean' | 'signal' | 'action';
}

export interface StrategyBlockType {
  type: string;
  label: string;
  category: BlockCategory;
  inputPorts: PortDefinition[];
  outputPorts: PortDefinition[];
  defaultConfig: Record<string, unknown>;
}

// Signal/indicator blocks
export const PriceBlock: StrategyBlockType = {
  type: 'signal.price',
  label: 'Price',
  category: 'signal',
  inputPorts: [],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'number' }],
  defaultConfig: { source: 'close' },
};

export const VolumeBlock: StrategyBlockType = {
  type: 'signal.volume',
  label: 'Volume',
  category: 'signal',
  inputPorts: [],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'number' }],
  defaultConfig: { source: 'volume' },
};

export const MomentumBlock: StrategyBlockType = {
  type: 'indicator.momentum',
  label: 'Momentum',
  category: 'indicator',
  inputPorts: [{ id: 'in', kind: 'input', dataType: 'number' }],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'number' }],
  defaultConfig: { lookback: 12 },
};

export const CustomIndicatorBlock: StrategyBlockType = {
  type: 'indicator.custom',
  label: 'Custom Indicator',
  category: 'indicator',
  inputPorts: [{ id: 'in', kind: 'input', dataType: 'number' }],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'number' }],
  defaultConfig: { expression: '' },
};

// Operator blocks
export const AndBlock: StrategyBlockType = {
  type: 'operator.and',
  label: 'AND',
  category: 'operator',
  inputPorts: [
    { id: 'left', kind: 'input', dataType: 'boolean' },
    { id: 'right', kind: 'input', dataType: 'boolean' },
  ],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'boolean' }],
  defaultConfig: {},
};

export const OrBlock: StrategyBlockType = {
  type: 'operator.or',
  label: 'OR',
  category: 'operator',
  inputPorts: [
    { id: 'left', kind: 'input', dataType: 'boolean' },
    { id: 'right', kind: 'input', dataType: 'boolean' },
  ],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'boolean' }],
  defaultConfig: {},
};

export const NotBlock: StrategyBlockType = {
  type: 'operator.not',
  label: 'NOT',
  category: 'operator',
  inputPorts: [{ id: 'in', kind: 'input', dataType: 'boolean' }],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'boolean' }],
  defaultConfig: {},
};

export const ThresholdBlock: StrategyBlockType = {
  type: 'operator.threshold',
  label: 'Threshold',
  category: 'operator',
  inputPorts: [{ id: 'in', kind: 'input', dataType: 'number' }],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'boolean' }],
  defaultConfig: { operator: '>', value: 0.0 },
};

// Action blocks
export const BuyActionBlock: StrategyBlockType = {
  type: 'action.buy',
  label: 'BUY',
  category: 'action',
  inputPorts: [{ id: 'trigger', kind: 'input', dataType: 'boolean' }],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'action' }],
  defaultConfig: { size: 100 },
};

export const SellActionBlock: StrategyBlockType = {
  type: 'action.sell',
  label: 'SELL',
  category: 'action',
  inputPorts: [{ id: 'trigger', kind: 'input', dataType: 'boolean' }],
  outputPorts: [{ id: 'out', kind: 'output', dataType: 'action' }],
  defaultConfig: { size: 100 },
};

export const STRATEGY_BLOCK_TYPES: StrategyBlockType[] = [
  PriceBlock,
  VolumeBlock,
  MomentumBlock,
  CustomIndicatorBlock,
  AndBlock,
  OrBlock,
  NotBlock,
  ThresholdBlock,
  BuyActionBlock,
  SellActionBlock,
];

