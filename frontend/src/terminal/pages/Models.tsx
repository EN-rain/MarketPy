import { useEffect, useMemo, useState } from 'react';
import { Cpu, RefreshCw, Loader2, Power } from 'lucide-react';
import { Card, CardHeader, CardBody, Badge, ProgressBar } from '../components/UI';
import { models, type Model } from '../data/mock';
import { cn } from '../utils/cn';

export default function Models() {
  const [modelRows, setModelRows] = useState<Model[]>(models);

  useEffect(() => {
    const timer = setInterval(() => {
      setModelRows(prev => prev.map(model => {
        if (model.status !== 'training') return model;
        return {
          ...model,
          status: 'active',
          lastTrained: 'just now',
          accuracy: Number.parseFloat(Math.min(98, model.accuracy + Math.random() * 2.5).toFixed(1)),
        };
      }));
    }, 6500);

    return () => clearInterval(timer);
  }, []);

  const active = useMemo(() => modelRows.filter(m => m.status === 'active').length, [modelRows]);
  const training = useMemo(() => modelRows.filter(m => m.status === 'training').length, [modelRows]);
  const avgAccuracy = useMemo(() => {
    const activeModels = modelRows.filter(m => m.status === 'active');
    if (activeModels.length === 0) return 0;
    return activeModels.reduce((sum, m) => sum + m.accuracy, 0) / activeModels.length;
  }, [modelRows]);

  const retrainModel = (modelId: string) => {
    setModelRows(prev => prev.map(model => model.id === modelId
      ? { ...model, status: 'training', lastTrained: 'running retrain...' }
      : model));
  };

  const toggleModelPower = (modelId: string) => {
    setModelRows(prev => prev.map(model => {
      if (model.id !== modelId) return model;
      if (model.status === 'training') return model;
      return {
        ...model,
        status: model.status === 'active' ? 'inactive' : 'active',
      };
    }));
  };

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Total Models</p>
            <p className="text-xl font-mono font-semibold text-text-primary">{modelRows.length}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Active</p>
            <p className="text-xl font-mono font-semibold text-accent">{active}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Training</p>
            <p className="text-xl font-mono font-semibold text-warn">{training}</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-3">
            <p className="text-[10px] uppercase tracking-wider text-text-muted font-medium mb-1">Avg Accuracy</p>
            <p className="text-xl font-mono font-semibold text-profit">{avgAccuracy.toFixed(1)}%</p>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {modelRows.map(model => (
          <Card key={model.id} className={cn(
            'transition-all',
            model.status === 'active' && 'border-accent/20',
            model.status === 'training' && 'border-warn/20',
          )}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className={cn(
                  'w-7 h-7 rounded-lg flex items-center justify-center',
                  model.status === 'active' ? 'bg-accent/10' : model.status === 'training' ? 'bg-warn/10' : 'bg-bg-tertiary',
                )}>
                  {model.status === 'training'
                    ? <Loader2 size={13} className="text-warn animate-spin" />
                    : <Cpu size={13} className={model.status === 'active' ? 'text-accent' : 'text-text-muted'} />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-text-primary truncate">{model.name}</p>
                  <p className="text-[10px] font-mono text-text-muted">{model.id}</p>
                </div>
              </div>
              <Badge variant={model.status === 'active' ? 'accent' : model.status === 'training' ? 'warning' : 'default'}>
                {model.status}
              </Badge>
            </CardHeader>
            <CardBody className="space-y-3">
              <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-text-muted">Type</p>
                  <p className="text-[11px] font-mono text-text-secondary">{model.type}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-text-muted">Horizon</p>
                  <p className="text-[11px] font-mono text-text-secondary">{model.horizon}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-text-muted">Parameters</p>
                  <p className="text-[11px] font-mono text-text-secondary">{model.params}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-wider text-text-muted">Dataset</p>
                  <p className="text-[11px] font-mono text-text-secondary truncate">{model.dataset}</p>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] uppercase tracking-wider text-text-muted">Accuracy</span>
                  <span className={cn(
                    'text-[11px] font-mono font-medium tabular-nums',
                    model.accuracy >= 80 ? 'text-profit' : model.accuracy >= 70 ? 'text-accent' : 'text-warn',
                  )}>
                    {model.accuracy}%
                  </span>
                </div>
                <ProgressBar
                  value={model.accuracy}
                  color={model.accuracy >= 80 ? 'profit' : model.accuracy >= 70 ? 'accent' : 'warn'}
                  className="h-1"
                />
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-border">
                <span className="text-[10px] text-text-muted">Trained {model.lastTrained}</span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => retrainModel(model.id)}
                    className="p-1 rounded hover:bg-bg-hover text-text-muted hover:text-text-secondary transition-all cursor-pointer"
                    title="Retrain"
                  >
                    <RefreshCw size={11} />
                  </button>
                  <button
                    onClick={() => toggleModelPower(model.id)}
                    className={cn(
                      'p-1 rounded hover:bg-bg-hover transition-all cursor-pointer',
                      model.status === 'active' ? 'text-accent hover:text-accent' : 'text-text-muted hover:text-text-secondary',
                    )}
                    title="Toggle"
                  >
                    <Power size={11} />
                  </button>
                </div>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
