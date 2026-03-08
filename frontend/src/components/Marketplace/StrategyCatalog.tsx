'use client';

import { useMemo, useState } from 'react';

export interface CatalogItem {
  id: string;
  name: string;
  author: string;
  asset_class: string;
  risk_level: string;
  description: string;
  methodology: string;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
}

export default function StrategyCatalog({ items }: { items: CatalogItem[] }) {
  const [assetClass, setAssetClass] = useState('');
  const [risk, setRisk] = useState('');

  const filtered = useMemo(() => {
    return items.filter((item) => {
      if (assetClass && item.asset_class !== assetClass) {
        return false;
      }
      if (risk && item.risk_level !== risk) {
        return false;
      }
      return true;
    });
  }, [assetClass, items, risk]);

  return (
    <section style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: 16, display: 'grid', gap: 10 }}>
      <h3 style={{ margin: 0 }}>Strategy Marketplace</h3>
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={assetClass} onChange={(e) => setAssetClass(e.target.value)} placeholder="Asset class" />
        <input value={risk} onChange={(e) => setRisk(e.target.value)} placeholder="Risk level" />
      </div>
      {filtered.map((item) => (
        <div key={item.id} style={{ border: '1px solid #f3f4f6', borderRadius: 8, padding: 10 }}>
          <div style={{ fontWeight: 700 }}>{item.name}</div>
          <div style={{ fontSize: 12, color: '#6b7280' }}>
            {item.author} | {item.asset_class} | {item.risk_level}
          </div>
          <div style={{ fontSize: 12, marginTop: 4 }}>{item.description}</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>
            Return={item.total_return.toFixed(4)} | Sharpe={item.sharpe_ratio.toFixed(4)} | Drawdown=
            {(item.max_drawdown * 100).toFixed(2)}%
          </div>
          <details style={{ marginTop: 6 }}>
            <summary>Methodology</summary>
            <div style={{ fontSize: 12 }}>{item.methodology}</div>
          </details>
        </div>
      ))}
    </section>
  );
}
