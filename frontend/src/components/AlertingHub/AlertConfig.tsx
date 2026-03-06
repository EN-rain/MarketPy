'use client';

import { useMemo, useState } from 'react';

type ConditionType = 'PRICE' | 'VOLUME' | 'VOLATILITY';
type Operator = 'GT' | 'LT' | 'EQ' | 'CROSSES_ABOVE' | 'CROSSES_BELOW';
type NotificationChannel = 'webhook' | 'telegram' | 'discord' | 'email';

export interface AlertConfigValue {
  marketId: string;
  conditionType: ConditionType;
  operator: Operator;
  threshold: number;
  cooldownSeconds: number;
  channels: NotificationChannel[];
}

const ALL_CHANNELS: NotificationChannel[] = ['webhook', 'telegram', 'discord', 'email'];

export default function AlertConfig({
  initialValue,
  onSave,
}: {
  initialValue?: Partial<AlertConfigValue>;
  onSave?: (value: AlertConfigValue) => void;
}) {
  const [marketId, setMarketId] = useState(initialValue?.marketId ?? 'BTCUSDT');
  const [conditionType, setConditionType] = useState<ConditionType>(
    initialValue?.conditionType ?? 'PRICE'
  );
  const [operator, setOperator] = useState<Operator>(initialValue?.operator ?? 'GT');
  const [threshold, setThreshold] = useState<number>(initialValue?.threshold ?? 0);
  const [cooldownSeconds, setCooldownSeconds] = useState<number>(
    initialValue?.cooldownSeconds ?? 60
  );
  const [channels, setChannels] = useState<NotificationChannel[]>(
    initialValue?.channels?.length ? initialValue.channels : ['webhook']
  );

  const canSave = useMemo(() => {
    return marketId.trim().length > 0 && Number.isFinite(threshold) && channels.length > 0;
  }, [channels.length, marketId, threshold]);

  const toggleChannel = (channel: NotificationChannel) => {
    setChannels((prev) => {
      if (prev.includes(channel)) {
        const next = prev.filter((entry) => entry !== channel);
        return next.length > 0 ? next : prev;
      }
      return [...prev, channel];
    });
  };

  const handleSave = () => {
    if (!canSave) {
      return;
    }
    onSave?.({
      marketId: marketId.trim(),
      conditionType,
      operator,
      threshold,
      cooldownSeconds: Math.max(0, cooldownSeconds),
      channels,
    });
  };

  return (
    <section
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: 12,
        padding: 16,
        background: '#ffffff',
        display: 'grid',
        gap: 12,
      }}
    >
      <h3 style={{ margin: 0 }}>Alert Configuration</h3>

      <label style={{ display: 'grid', gap: 4 }}>
        <span style={{ fontSize: 12, color: '#6b7280' }}>Market ID</span>
        <input
          value={marketId}
          onChange={(event) => setMarketId(event.target.value)}
          placeholder="BTCUSDT"
          style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px' }}
        />
      </label>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(140px, 1fr))', gap: 8 }}>
        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Condition Type</span>
          <select
            value={conditionType}
            onChange={(event) => setConditionType(event.target.value as ConditionType)}
            style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px' }}
          >
            <option value="PRICE">Price</option>
            <option value="VOLUME">Volume</option>
            <option value="VOLATILITY">Volatility</option>
          </select>
        </label>

        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Operator</span>
          <select
            value={operator}
            onChange={(event) => setOperator(event.target.value as Operator)}
            style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px' }}
          >
            <option value="GT">&gt; Greater Than</option>
            <option value="LT">&lt; Less Than</option>
            <option value="EQ">= Equal To</option>
            <option value="CROSSES_ABOVE">Crosses Above</option>
            <option value="CROSSES_BELOW">Crosses Below</option>
          </select>
        </label>

        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Threshold</span>
          <input
            type="number"
            step="0.0001"
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
            style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px' }}
          />
        </label>

        <label style={{ display: 'grid', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Cooldown (seconds)</span>
          <input
            type="number"
            min={0}
            step={1}
            value={cooldownSeconds}
            onChange={(event) => setCooldownSeconds(Number(event.target.value))}
            style={{ border: '1px solid #d1d5db', borderRadius: 8, padding: '8px 10px' }}
          />
        </label>
      </div>

      <div style={{ display: 'grid', gap: 6 }}>
        <span style={{ fontSize: 12, color: '#6b7280' }}>Notification Channels</span>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {ALL_CHANNELS.map((channel) => (
            <label key={channel} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <input
                type="checkbox"
                checked={channels.includes(channel)}
                onChange={() => toggleChannel(channel)}
              />
              {channel}
            </label>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          onClick={handleSave}
          disabled={!canSave}
          style={{
            border: '1px solid #111827',
            borderRadius: 8,
            background: canSave ? '#111827' : '#9ca3af',
            color: '#ffffff',
            padding: '8px 12px',
            cursor: canSave ? 'pointer' : 'not-allowed',
          }}
        >
          Save Alert
        </button>
      </div>
    </section>
  );
}
