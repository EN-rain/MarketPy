'use client';

import { useMemo, useState } from 'react';
import type { DragEvent } from 'react';
import {
  STRATEGY_BLOCK_TYPES,
  type StrategyBlockType,
} from './blockTypes';
import styles from './StrategyCanvas.module.css';

export interface StrategyBlock {
  id: string;
  type: string;
  category: 'signal' | 'indicator' | 'operator' | 'action';
  config: Record<string, unknown>;
  position: { x: number; y: number };
}

export interface Connection {
  from: { blockId: string; outputPort: string };
  to: { blockId: string; inputPort: string };
}

function makeId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function blockByType(type: string): StrategyBlockType | undefined {
  return STRATEGY_BLOCK_TYPES.find((entry) => entry.type === type);
}

export default function StrategyCanvas() {
  const [blocks, setBlocks] = useState<StrategyBlock[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  const paletteByCategory = useMemo(() => {
    return {
      signal: STRATEGY_BLOCK_TYPES.filter((entry) => entry.category === 'signal'),
      indicator: STRATEGY_BLOCK_TYPES.filter((entry) => entry.category === 'indicator'),
      operator: STRATEGY_BLOCK_TYPES.filter((entry) => entry.category === 'operator'),
      action: STRATEGY_BLOCK_TYPES.filter((entry) => entry.category === 'action'),
    };
  }, []);

  const onDragStart = (event: DragEvent, blockType: StrategyBlockType) => {
    event.dataTransfer.setData('application/strategy-block-type', blockType.type);
  };

  const onDropOnCanvas = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const type = event.dataTransfer.getData('application/strategy-block-type');
    const definition = blockByType(type);
    if (!definition) {
      return;
    }

    const rect = event.currentTarget.getBoundingClientRect();
    const block: StrategyBlock = {
      id: makeId('block'),
      type: definition.type,
      category: definition.category,
      config: { ...definition.defaultConfig },
      position: {
        x: Math.max(8, event.clientX - rect.left - 80),
        y: Math.max(8, event.clientY - rect.top - 22),
      },
    };

    setBlocks((prev) => [...prev, block]);
  };

  const toggleSelection = (blockId: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(blockId)) {
        return prev.filter((id) => id !== blockId);
      }
      if (prev.length >= 2) {
        return [prev[1], blockId];
      }
      return [...prev, blockId];
    });
  };

  const connectSelected = () => {
    if (selectedIds.length !== 2) {
      return;
    }
    const [fromId, toId] = selectedIds;
    const fromBlock = blocks.find((entry) => entry.id === fromId);
    const toBlock = blocks.find((entry) => entry.id === toId);
    if (!fromBlock || !toBlock) {
      return;
    }

    const fromDef = blockByType(fromBlock.type);
    const toDef = blockByType(toBlock.type);
    if (!fromDef || !toDef || fromDef.outputPorts.length === 0 || toDef.inputPorts.length === 0) {
      return;
    }

    const connection: Connection = {
      from: { blockId: fromId, outputPort: fromDef.outputPorts[0].id },
      to: { blockId: toId, inputPort: toDef.inputPorts[0].id },
    };
    setConnections((prev) => [...prev, connection]);
    setSelectedIds([]);
  };

  const clearCanvas = () => {
    setBlocks([]);
    setConnections([]);
    setSelectedIds([]);
  };

  return (
    <div className={styles.container}>
      <aside className={styles.palette}>
        <h3>Block Palette</h3>
        {Object.entries(paletteByCategory).map(([category, items]) => (
          <div key={category}>
            <strong>{category.toUpperCase()}</strong>
            <div className={styles.paletteList}>
              {items.map((item) => (
                <div
                  key={item.type}
                  className={styles.paletteItem}
                  draggable
                  onDragStart={(event) => onDragStart(event, item)}
                >
                  {item.label}
                </div>
              ))}
            </div>
          </div>
        ))}
      </aside>

      <div
        className={styles.canvas}
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDropOnCanvas}
      >
        <div className={styles.toolbar}>
          <button onClick={connectSelected} type="button">
            Connect Selected
          </button>
          <button onClick={clearCanvas} type="button">
            Clear
          </button>
        </div>

        {blocks.map((block) => (
          <div
            key={block.id}
            className={`${styles.block} ${selectedIds.includes(block.id) ? styles.selected : ''}`}
            style={{ left: block.position.x, top: block.position.y }}
            onClick={() => toggleSelection(block.id)}
            role="button"
            tabIndex={0}
          >
            <div className={styles.blockTitle}>{block.type}</div>
            <div className={styles.blockMeta}>id: {block.id}</div>
          </div>
        ))}

        <div className={styles.connectionList}>
          <strong>Connections</strong>
          {connections.length === 0 ? (
            <div>No connections</div>
          ) : (
            connections.map((connection, index) => (
              <div key={`${connection.from.blockId}-${connection.to.blockId}-${index}`}>
                {connection.from.blockId}:{connection.from.outputPort} -&gt;{' '}
                {connection.to.blockId}:{connection.to.inputPort}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
