'use client'

import { useState, useCallback } from 'react'
import { 
  LayoutDashboard, 
  TrendingUp, 
  FlaskConical, 
  History, 
  Brain, 
  Database,
  ChevronRight,
  Activity,
  BarChart3,
  TrendingDown,
  DollarSign,
  Percent,
  Clock,
  Zap,
  Target,
  RefreshCw,
  Settings,
  Bell,
  Search,
  Plus,
  Play,
  Pause,
  Trash2,
  Download,
  Upload,
  Filter,
  X,
  Check,
  AlertTriangle,
  Terminal,
  Layers,
  Cpu,
  HardDrive,
  ArrowUpRight,
  ArrowDownRight,
  CircleDot,
  GitBranch,
  Copy,
  Info,
  Eye,
  FileText
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useToast } from '@/hooks/use-toast'
import { ToastAction } from '@/components/ui/toast'
import { 
  LineChart as RechartsLineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip as RechartsTooltip, 
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  ComposedChart
} from 'recharts'

// Types
type NavItem = 'overview' | 'markets' | 'paper-trading' | 'backtests' | 'models' | 'database'
type OrderSide = 'LONG' | 'SHORT'
type OrderType = 'market' | 'limit'

interface Position {
  id: string
  symbol: string
  side: OrderSide
  entry: number
  current: number
  size: number
  pnl: number
  pnlPercent: number
  leverage: number
  timestamp: Date
}

interface Trade {
  id: string
  time: string
  symbol: string
  side: 'BUY' | 'SELL'
  price: number
  size: number
  pnl: number | null
  timestamp: Date
}

interface Backtest {
  id: string
  name: string
  status: 'completed' | 'running' | 'queued' | 'failed'
  return: number | null
  sharpe: number | null
  maxDD: number | null
  winRate: number | null
  trades: number | null
  created: string
  progress?: number
}

interface Model {
  id: string
  name: string
  type: 'LSTM' | 'Transformer' | 'XGBoost' | 'Ensemble'
  accuracy: number
  lastTrained: string
  status: 'active' | 'training' | 'inactive'
  predictions: number
}

// Helper functions
const generateId = () => Math.random().toString(36).substr(2, 9)

const formatTime = (date: Date) => {
  return date.toLocaleTimeString('en-US', { hour12: false })
}

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)
}

// Mock market data with current prices
const marketPrices: Record<string, { price: number; change: number }> = {
  'BTC/USDT': { price: 67842.50, change: 2.34 },
  'ETH/USDT': { price: 3456.78, change: -0.89 },
  'SOL/USDT': { price: 178.92, change: 5.67 },
  'BNB/USDT': { price: 612.34, change: 1.23 },
  'XRP/USDT': { price: 0.5234, change: -2.15 },
  'ADA/USDT': { price: 0.4567, change: 3.45 },
  'AVAX/USDT': { price: 38.92, change: 4.12 },
  'DOT/USDT': { price: 7.23, change: -1.34 },
}

const marketData = Object.entries(marketPrices).map(([symbol, data]) => ({
  symbol,
  price: data.price,
  change24h: data.change,
  volume: ['28.4B', '12.1B', '4.2B', '2.8B', '1.9B', '890M', '720M', '480M'][Object.keys(marketPrices).indexOf(symbol)],
  high: data.price * 1.02,
  low: data.price * 0.98,
}))

const performanceData = [
  { date: 'Mon', pnl: 1250, cumulative: 1250, volume: 45000 },
  { date: 'Tue', pnl: -340, cumulative: 910, volume: 38000 },
  { date: 'Wed', pnl: 2100, cumulative: 3010, volume: 52000 },
  { date: 'Thu', pnl: 890, cumulative: 3900, volume: 41000 },
  { date: 'Fri', pnl: -120, cumulative: 3780, volume: 35000 },
  { date: 'Sat', pnl: 1560, cumulative: 5340, volume: 48000 },
  { date: 'Sun', pnl: 2340, cumulative: 7680, volume: 55000 },
]

const dbTables = [
  { name: 'ohlcv_1m', rows: 2456789, size: '1.2 GB', lastUpdate: '2s ago' },
  { name: 'ohlcv_5m', rows: 491356, size: '245 MB', lastUpdate: '5s ago' },
  { name: 'ohlcv_1h', rows: 40946, size: '21 MB', lastUpdate: '1m ago' },
  { name: 'trades', rows: 156782, size: '89 MB', lastUpdate: 'Real-time' },
  { name: 'predictions', rows: 89234, size: '45 MB', lastUpdate: '30s ago' },
  { name: 'signals', rows: 34567, size: '18 MB', lastUpdate: '1m ago' },
]

// Components
function NavLink({ icon, label, active, onClick, badge }: { icon: React.ReactNode; label: string; active?: boolean; onClick?: () => void; badge?: string }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200",
        "hover:bg-sidebar-accent group relative",
        active 
          ? "bg-sidebar-accent text-accent glow-accent-strong" 
          : "text-sidebar-foreground/70 hover:text-sidebar-foreground"
      )}
    >
      <span className={cn(
        "transition-colors",
        active ? "text-accent" : "text-muted-foreground group-hover:text-sidebar-foreground"
      )}>
        {icon}
      </span>
      <span className="flex-1 text-left">{label}</span>
      {badge && (
        <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 bg-accent/10 border-accent/20 text-accent">
          {badge}
        </Badge>
      )}
      {active && <ChevronRight className="w-4 h-4 text-accent" />}
    </button>
  )
}

function StatusIndicator({ status, label }: { status: 'connected' | 'disconnected' | 'pending'; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={cn("status-dot", status)} />
      <span className="text-muted-foreground">{label}</span>
    </div>
  )
}

function StatCard({ title, value, change, changePercent, icon, trend }: {
  title: string
  value: string | number
  change?: number
  changePercent?: number
  icon?: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
}) {
  return (
    <Card className="terminal-card bg-card/50 backdrop-blur-sm">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground uppercase tracking-wider">{title}</p>
            <p className="text-xl font-semibold font-mono-data">{value}</p>
            {(change !== undefined || changePercent !== undefined) && (
              <div className={cn(
                "flex items-center gap-1 text-xs font-mono-data",
                trend === 'up' ? "pnl-positive" : trend === 'down' ? "pnl-negative" : "text-muted-foreground"
              )}>
                {trend === 'up' && <ArrowUpRight className="w-3 h-3" />}
                {trend === 'down' && <ArrowDownRight className="w-3 h-3" />}
                {change !== undefined && <span>${change >= 0 ? '+' : ''}{change.toLocaleString()}</span>}
                {changePercent !== undefined && (
                  <span className="text-muted-foreground">({changePercent >= 0 ? '+' : ''}{changePercent}%)</span>
                )}
              </div>
            )}
          </div>
          {icon && (
            <div className="p-2 rounded-lg bg-muted/50 text-muted-foreground">
              {icon}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function MiniChart({ data, color, height = 40 }: { data: number[]; color?: string; height?: number }) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  
  return (
    <svg width="100%" height={height} className="overflow-visible">
      <polyline
        fill="none"
        stroke={color || 'oklch(0.70 0.15 195)'}
        strokeWidth="1.5"
        points={data.map((v, i) => `${(i / (data.length - 1)) * 100},${height - ((v - min) / range) * height}`).join(' ')}
      />
    </svg>
  )
}

function PnLChart() {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={performanceData}>
        <defs>
          <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="oklch(0.70 0.15 195)" stopOpacity={0.3}/>
            <stop offset="95%" stopColor="oklch(0.70 0.15 195)" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.25 0.015 260)" />
        <XAxis dataKey="date" stroke="oklch(0.55 0.01 260)" fontSize={11} fontFamily="var(--font-geist-mono)" />
        <YAxis stroke="oklch(0.55 0.01 260)" fontSize={11} fontFamily="var(--font-geist-mono)" />
        <RechartsTooltip 
          contentStyle={{ 
            backgroundColor: 'oklch(0.15 0.012 260)', 
            border: '1px solid oklch(0.25 0.015 260)',
            borderRadius: '6px',
            fontSize: '12px'
          }}
          labelStyle={{ color: 'oklch(0.90 0.01 260)' }}
        />
        <Bar dataKey="volume" fill="oklch(0.30 0.02 260)" opacity={0.3} />
        <Line type="monotone" dataKey="cumulative" stroke="oklch(0.70 0.15 195)" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="pnl" stroke="oklch(0.60 0.15 195)" strokeWidth={1.5} dot={false} strokeDasharray="4 4" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

// New Order Dialog
function NewOrderDialog({ 
  onPlaceOrder, 
  positions 
}: { 
  onPlaceOrder: (symbol: string, side: OrderSide, size: number, leverage: number) => void
  positions: Position[]
}) {
  const [open, setOpen] = useState(false)
  const [symbol, setSymbol] = useState('BTC/USDT')
  const [side, setSide] = useState<OrderSide>('LONG')
  const [size, setSize] = useState('')
  const [leverage, setLeverage] = useState(1)
  const { toast } = useToast()

  const handlePlaceOrder = () => {
    const sizeNum = parseFloat(size)
    if (!sizeNum || sizeNum <= 0) {
      toast({
        title: "Invalid size",
        description: "Please enter a valid position size",
        variant: "destructive",
      })
      return
    }

    onPlaceOrder(symbol, side, sizeNum, leverage)
    setOpen(false)
    setSize('')
    setLeverage(1)
    
    toast({
      title: "Order Placed",
      description: `${side} ${sizeNum} ${symbol.split('/')[0]} at ${leverage}x leverage`,
      action: <ToastAction altText="View">View Position</ToastAction>,
    })
  }

  const currentPrice = marketPrices[symbol]?.price || 0

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="h-8 bg-accent text-accent-foreground hover:bg-accent/80">
          <Plus className="w-3 h-3 mr-1" />
          New Trade
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <DialogTitle>Place New Order</DialogTitle>
          <DialogDescription>
            Enter your trade details below
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Symbol</Label>
            <Select value={symbol} onValueChange={setSymbol}>
              <SelectTrigger className="bg-muted/30 border-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.keys(marketPrices).map((s) => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Side</Label>
            <div className="grid grid-cols-2 gap-2">
              <Button 
                variant={side === 'LONG' ? 'default' : 'outline'}
                className={cn(side === 'LONG' && "bg-green-600 hover:bg-green-700 text-white")}
                onClick={() => setSide('LONG')}
              >
                <TrendingUp className="w-3 h-3 mr-1" />
                Long
              </Button>
              <Button 
                variant={side === 'SHORT' ? 'default' : 'outline'}
                className={cn(side === 'SHORT' && "bg-red-600 hover:bg-red-700 text-white")}
                onClick={() => setSide('SHORT')}
              >
                <TrendingDown className="w-3 h-3 mr-1" />
                Short
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Size (USDT)</Label>
            <Input 
              type="number" 
              placeholder="1000" 
              value={size}
              onChange={(e) => setSize(e.target.value)}
              className="bg-muted/30 border-0" 
            />
            <div className="flex gap-1">
              {[100, 500, 1000, 5000].map((preset) => (
                <Button 
                  key={preset} 
                  variant="outline" 
                  size="sm" 
                  className="h-6 text-[10px] flex-1"
                  onClick={() => setSize(preset.toString())}
                >
                  ${preset}
                </Button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Leverage</Label>
            <div className="flex gap-1">
              {[1, 3, 5, 10, 20].map((lev) => (
                <Button 
                  key={lev} 
                  variant={leverage === lev ? 'default' : 'outline'}
                  size="sm" 
                  className={cn("h-7 text-xs flex-1", leverage === lev && "bg-accent text-accent-foreground")}
                  onClick={() => setLeverage(lev)}
                >
                  {lev}x
                </Button>
              ))}
            </div>
          </div>

          {size && (
            <div className="p-3 rounded bg-muted/30 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Entry Price</span>
                <span className="font-mono-data">{formatCurrency(currentPrice)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Position Size</span>
                <span className="font-mono-data">{(parseFloat(size) / currentPrice).toFixed(6)} {symbol.split('/')[0]}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Margin Required</span>
                <span className="font-mono-data">{formatCurrency(parseFloat(size) / leverage)}</span>
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button className="bg-accent text-accent-foreground hover:bg-accent/80" onClick={handlePlaceOrder}>
            Place Order
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// New Backtest Dialog
function NewBacktestDialog({ onCreateBacktest }: { onCreateBacktest: (name: string, strategy: string) => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [strategy, setStrategy] = useState('trend')
  const { toast } = useToast()

  const handleCreate = () => {
    if (!name.trim()) {
      toast({
        title: "Name required",
        description: "Please enter a name for your backtest",
        variant: "destructive",
      })
      return
    }

    onCreateBacktest(name, strategy)
    setOpen(false)
    setName('')
    setStrategy('trend')
    
    toast({
      title: "Backtest Created",
      description: `"${name}" has been added to the queue`,
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="h-8 bg-accent text-accent-foreground hover:bg-accent/80">
          <Plus className="w-3 h-3 mr-1" />
          New Backtest
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <DialogTitle>Create New Backtest</DialogTitle>
          <DialogDescription>
            Configure your backtesting parameters
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Backtest Name</Label>
            <Input 
              placeholder="My Strategy" 
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="bg-muted/30 border-0" 
            />
          </div>

          <div className="space-y-2">
            <Label>Strategy Type</Label>
            <Select value={strategy} onValueChange={setStrategy}>
              <SelectTrigger className="bg-muted/30 border-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="trend">Trend Following</SelectItem>
                <SelectItem value="mean-reversion">Mean Reversion</SelectItem>
                <SelectItem value="momentum">Momentum</SelectItem>
                <SelectItem value="grid">Grid Trading</SelectItem>
                <SelectItem value="arbitrage">Statistical Arbitrage</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Assets</Label>
            <div className="flex flex-wrap gap-1">
              {['BTC', 'ETH', 'SOL', 'BNB'].map((asset) => (
                <Badge key={asset} variant="outline" className="cursor-pointer hover:bg-accent/10">
                  {asset}
                </Badge>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <Input type="date" className="bg-muted/30 border-0 h-9" />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <Input type="date" className="bg-muted/30 border-0 h-9" />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <Label>Include AI Predictions</Label>
            <Switch />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button className="bg-accent text-accent-foreground hover:bg-accent/80" onClick={handleCreate}>
            Create Backtest
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// New Model Dialog
function NewModelDialog({ onTrainModel }: { onTrainModel: (name: string, type: Model['type']) => void }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [type, setType] = useState<Model['type']>('LSTM')
  const { toast } = useToast()

  const handleTrain = () => {
    if (!name.trim()) {
      toast({
        title: "Name required",
        description: "Please enter a name for your model",
        variant: "destructive",
      })
      return
    }

    onTrainModel(name, type)
    setOpen(false)
    setName('')
    setType('LSTM')
    
    toast({
      title: "Model Training Started",
      description: `"${name}" is now being trained`,
    })
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" className="h-8 bg-accent text-accent-foreground hover:bg-accent/80">
          <Plus className="w-3 h-3 mr-1" />
          Train New
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md bg-card border-border">
        <DialogHeader>
          <DialogTitle>Train New Model</DialogTitle>
          <DialogDescription>
            Configure your AI prediction model
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Model Name</Label>
            <Input 
              placeholder="My Predictor" 
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="bg-muted/30 border-0" 
            />
          </div>

          <div className="space-y-2">
            <Label>Model Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as Model['type'])}>
              <SelectTrigger className="bg-muted/30 border-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="LSTM">LSTM (Long Short-Term Memory)</SelectItem>
                <SelectItem value="Transformer">Transformer</SelectItem>
                <SelectItem value="XGBoost">XGBoost Classifier</SelectItem>
                <SelectItem value="Ensemble">Ensemble Meta</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Training Data</Label>
            <Select defaultValue="all">
              <SelectTrigger className="bg-muted/30 border-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Available Data</SelectItem>
                <SelectItem value="btc">BTC/USDT Only</SelectItem>
                <SelectItem value="eth">ETH/USDT Only</SelectItem>
                <SelectItem value="multi">Multi-Asset</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Prediction Horizon</Label>
            <div className="flex gap-1">
              {['1m', '5m', '15m', '1h', '4h', '1d'].map((h) => (
                <Button key={h} variant="outline" size="sm" className="h-7 text-xs flex-1">
                  {h}
                </Button>
              ))}
            </div>
          </div>

          <Alert className="bg-muted/30 border-0">
            <Cpu className="w-4 h-4" />
            <AlertDescription className="text-xs">
              Training typically takes 15-45 minutes depending on model complexity and data size.
            </AlertDescription>
          </Alert>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button className="bg-accent text-accent-foreground hover:bg-accent/80" onClick={handleTrain}>
            Start Training
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Backtest Details Dialog
function BacktestDetailsDialog({ backtest }: { backtest: Backtest }) {
  const [open, setOpen] = useState(false)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="h-6 text-xs text-accent">
          View Details
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl bg-card border-border">
        <DialogHeader>
          <DialogTitle>{backtest.name}</DialogTitle>
          <DialogDescription>
            Backtest ID: {backtest.id}
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="p-3 rounded bg-muted/30">
              <div className="text-xs text-muted-foreground">Total Return</div>
              <div className="text-xl font-mono-data pnl-positive">+{backtest.return}%</div>
            </div>
            <div className="p-3 rounded bg-muted/30">
              <div className="text-xs text-muted-foreground">Sharpe Ratio</div>
              <div className="text-xl font-mono-data">{backtest.sharpe}</div>
            </div>
            <div className="p-3 rounded bg-muted/30">
              <div className="text-xs text-muted-foreground">Max Drawdown</div>
              <div className="text-xl font-mono-data pnl-negative">{backtest.maxDD}%</div>
            </div>
            <div className="p-3 rounded bg-muted/30">
              <div className="text-xs text-muted-foreground">Win Rate</div>
              <div className="text-xl font-mono-data">{backtest.winRate}%</div>
            </div>
          </div>
          
          <div className="h-64 rounded bg-muted/20 flex items-center justify-center text-muted-foreground">
            <div className="text-center">
              <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Equity Curve Visualization</p>
            </div>
          </div>

          <div className="mt-4">
            <h4 className="text-sm font-medium mb-2">Trade History</h4>
            <ScrollArea className="h-32">
              <div className="text-xs text-muted-foreground font-mono">
                {Array.from({ length: 10 }).map((_, i) => (
                  <div key={i} className="py-1 border-b border-border/30">
                    [{new Date(Date.now() - i * 3600000).toLocaleTimeString()}] {' '}
                    {i % 2 === 0 ? 'BUY' : 'SELL'} {Math.random() > 0.5 ? 'BTC' : 'ETH'} @ ${Math.floor(60000 + Math.random() * 10000)}
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Close</Button>
          <Button className="bg-accent text-accent-foreground hover:bg-accent/80">
            <Play className="w-3 h-3 mr-1" />
            Deploy to Paper Trading
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Model Details Dialog
function ModelDetailsDialog({ model }: { model: Model }) {
  const [open, setOpen] = useState(false)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="h-6 text-xs">Details</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg bg-card border-border">
        <DialogHeader>
          <DialogTitle>{model.name}</DialogTitle>
          <DialogDescription>
            Model ID: {model.id} • Type: {model.type}
          </DialogDescription>
        </DialogHeader>
        <div className="py-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 rounded bg-muted/30">
              <div className="text-xs text-muted-foreground">Accuracy</div>
              <div className="text-2xl font-mono-data text-accent">{model.accuracy}%</div>
            </div>
            <div className="p-3 rounded bg-muted/30">
              <div className="text-xs text-muted-foreground">Predictions</div>
              <div className="text-2xl font-mono-data">{model.predictions.toLocaleString()}</div>
            </div>
          </div>

          <div className="p-3 rounded bg-muted/30">
            <div className="text-xs text-muted-foreground mb-2">Performance Metrics</div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Precision</span>
                <span className="font-mono-data">0.72</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Recall</span>
                <span className="font-mono-data">0.68</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">F1 Score</span>
                <span className="font-mono-data">0.70</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">AUC-ROC</span>
                <span className="font-mono-data">0.76</span>
              </div>
            </div>
          </div>

          <div className="p-3 rounded bg-muted/30">
            <div className="text-xs text-muted-foreground mb-2">Training Info</div>
            <div className="text-sm space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Last Trained</span>
                <span>{model.lastTrained}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Training Duration</span>
                <span>23 minutes</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Data Points Used</span>
                <span>1.2M</span>
              </div>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Close</Button>
          <Button variant="outline">
            <FileText className="w-3 h-3 mr-1" />
            Export
          </Button>
          <Button className="bg-accent text-accent-foreground hover:bg-accent/80">
            <RefreshCw className="w-3 h-3 mr-1" />
            Retrain
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Main View Components
function OverviewView({ 
  positions, 
  trades, 
  onTradeClick 
}: { 
  positions: Position[]
  trades: Trade[]
  onTradeClick: () => void
}) {
  const totalPnL = positions.reduce((sum, p) => sum + p.pnl, 0)
  
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          title="Portfolio Value" 
          value={formatCurrency(125847.32 + totalPnL)}
          change={Math.round(totalPnL)}
          changePercent={2.31}
          trend={totalPnL >= 0 ? 'up' : 'down'}
          icon={<DollarSign className="w-4 h-4" />}
        />
        <StatCard 
          title="Open Trades" 
          value={positions.length}
          icon={<Activity className="w-4 h-4" />}
        />
        <StatCard 
          title="Win Rate" 
          value="67.8%"
          icon={<Target className="w-4 h-4" />}
        />
        <StatCard 
          title="Sharpe Ratio" 
          value="2.14"
          icon={<BarChart3 className="w-4 h-4" />}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="terminal-card bg-card/50 backdrop-blur-sm lg:col-span-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Cumulative PnL</CardTitle>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" className="h-7 text-xs">1D</Button>
                <Button variant="ghost" size="sm" className="h-7 text-xs bg-accent/10 text-accent">1W</Button>
                <Button variant="ghost" size="sm" className="h-7 text-xs">1M</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <PnLChart />
          </CardContent>
        </Card>

        <Card className="terminal-card bg-card/50 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Top Performers</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {marketData.slice(0, 4).map((coin) => (
              <div key={coin.symbol} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono-data">{coin.symbol}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono-data">${coin.price.toLocaleString()}</span>
                  <span className={cn(
                    "text-xs font-mono-data",
                    coin.change24h >= 0 ? "pnl-positive" : "pnl-negative"
                  )}>
                    {coin.change24h >= 0 ? '+' : ''}{coin.change24h}%
                  </span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Positions & Recent Trades */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="terminal-card bg-card/50 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Open Positions</CardTitle>
              <Badge variant="outline" className="text-[10px]">{positions.length} active</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground text-sm">
                No open positions. Start trading!
              </div>
            ) : (
              <div className="space-y-2">
                {positions.map((pos) => (
                  <div key={pos.id} className="flex items-center justify-between p-2 rounded bg-muted/30 hover:bg-muted/50 transition-colors">
                    <div className="flex items-center gap-3">
                      <Badge variant={pos.side === 'LONG' ? 'default' : 'destructive'} className="text-[10px] px-1.5">
                        {pos.side}
                      </Badge>
                      <div>
                        <span className="text-xs font-mono-data">{pos.symbol}</span>
                        <div className="text-[10px] text-muted-foreground">{pos.leverage}x • ${pos.entry.toLocaleString()}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={cn("text-xs font-mono-data", pos.pnl >= 0 ? "pnl-positive" : "pnl-negative")}>
                        {pos.pnl >= 0 ? '+' : ''}${pos.pnl.toFixed(2)}
                      </span>
                      <div className={cn("text-[10px]", pos.pnlPercent >= 0 ? "pnl-positive" : "pnl-negative")}>
                        {pos.pnlPercent >= 0 ? '+' : ''}{pos.pnlPercent.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="terminal-card bg-card/50 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Recent Trades</CardTitle>
              <Button variant="ghost" size="sm" className="h-6 text-xs text-accent" onClick={onTradeClick}>
                View All
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {trades.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground text-sm">
                No recent trades
              </div>
            ) : (
              <div className="space-y-1">
                {trades.slice(0, 5).map((trade) => (
                  <div key={trade.id} className="flex items-center justify-between p-2 rounded hover:bg-muted/30 transition-colors">
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] font-mono-data text-muted-foreground">{trade.time}</span>
                      <Badge variant={trade.side === 'BUY' ? 'default' : 'secondary'} className="text-[10px] px-1.5">
                        {trade.side}
                      </Badge>
                      <span className="text-xs font-mono-data">{trade.symbol}</span>
                    </div>
                    <div className="text-right flex items-center gap-4">
                      <span className="text-xs font-mono-data">${trade.price.toLocaleString()}</span>
                      {trade.pnl !== null && (
                        <span className={cn("text-xs font-mono-data w-16 text-right", trade.pnl >= 0 ? "pnl-positive" : "pnl-negative")}>
                          {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* System Log */}
      <Card className="terminal-card bg-card/50 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Terminal className="w-4 h-4 text-accent" />
              System Log
            </CardTitle>
            <Badge variant="outline" className="text-[10px] bg-muted/50">Live</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-32">
            <div className="space-y-1 font-mono text-xs">
              {trades.slice(0, 5).map((trade, i) => (
                <div key={i} className="text-muted-foreground">
                  [{trade.time}] <span className="pnl-positive">INFO</span> Order executed: {trade.side} {trade.size} {trade.symbol.split('/')[0]} @ ${trade.price.toLocaleString()}
                </div>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}

function MarketsView({ onTradeSymbol }: { onTradeSymbol: (symbol: string) => void }) {
  const [searchTerm, setSearchTerm] = useState('')
  
  const filteredMarkets = marketData.filter(m => 
    m.symbol.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">Market Overview</h2>
          <Badge variant="outline" className="text-[10px]">Live</Badge>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input 
              placeholder="Search markets..." 
              className="pl-8 h-8 w-48 bg-muted/30 border-0 text-xs"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
      </div>

      <Card className="terminal-card bg-card/50 backdrop-blur-sm">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Symbol</th>
                  <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Price</th>
                  <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">24h Change</th>
                  <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Volume</th>
                  <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">24h High</th>
                  <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">24h Low</th>
                  <th className="text-center p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredMarkets.map((coin, i) => (
                  <tr key={i} className="border-b border-border/30 hover:bg-muted/20 transition-colors">
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-muted flex items-center justify-center text-[10px] font-bold">
                          {coin.symbol.split('/')[0].slice(0, 2)}
                        </div>
                        <span className="font-mono-data text-sm">{coin.symbol}</span>
                      </div>
                    </td>
                    <td className="p-3 text-right font-mono-data">${coin.price.toLocaleString()}</td>
                    <td className={cn("p-3 text-right font-mono-data", coin.change24h >= 0 ? "pnl-positive" : "pnl-negative")}>
                      {coin.change24h >= 0 ? '+' : ''}{coin.change24h}%
                    </td>
                    <td className="p-3 text-right font-mono-data text-muted-foreground">{coin.volume}</td>
                    <td className="p-3 text-right font-mono-data text-muted-foreground">${coin.high.toLocaleString()}</td>
                    <td className="p-3 text-right font-mono-data text-muted-foreground">${coin.low.toLocaleString()}</td>
                    <td className="p-3 text-center">
                      <Button 
                        size="sm" 
                        variant="ghost" 
                        className="h-7 text-xs text-accent hover:text-accent"
                        onClick={() => onTradeSymbol(coin.symbol)}
                      >
                        Trade
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Market Heatmap */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {filteredMarkets.slice(0, 8).map((coin, i) => (
          <Card key={i} className={cn(
            "terminal-card bg-card/50 backdrop-blur-sm cursor-pointer transition-all",
            coin.change24h >= 0 ? "hover:border-green-500/30" : "hover:border-red-500/30"
          )}>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono-data text-sm">{coin.symbol}</span>
                <Badge variant="outline" className={cn(
                  "text-[10px]",
                  coin.change24h >= 0 ? "border-green-500/30 text-green-400" : "border-red-500/30 text-red-400"
                )}>
                  {coin.change24h >= 0 ? '+' : ''}{coin.change24h}%
                </Badge>
              </div>
              <div className="text-xl font-mono-data font-semibold">${coin.price.toLocaleString()}</div>
              <div className="mt-2 h-8">
                <MiniChart 
                  data={Array.from({length: 20}, () => coin.price * (1 + (Math.random() - 0.5) * 0.02))} 
                  color={coin.change24h >= 0 ? 'oklch(0.70 0.18 145)' : 'oklch(0.65 0.20 25)'}
                />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function PaperTradingView({
  positions,
  trades,
  onPlaceOrder,
  onClosePosition,
  onCloseAllPositions
}: {
  positions: Position[]
  trades: Trade[]
  onPlaceOrder: (symbol: string, side: OrderSide, size: number, leverage: number) => void
  onClosePosition: (id: string) => void
  onCloseAllPositions: () => void
}) {
  const { toast } = useToast()
  const totalPnL = positions.reduce((sum, p) => sum + p.pnl, 0)
  const unrealizedPnL = positions.reduce((sum, p) => sum + p.pnl, 0)

  const handleClosePosition = (id: string) => {
    const position = positions.find(p => p.id === id)
    if (position) {
      onClosePosition(id)
      toast({
        title: "Position Closed",
        description: `Closed ${position.side} ${position.symbol} position`,
      })
    }
  }

  const handleCloseAll = () => {
    onCloseAllPositions()
    toast({
      title: "All Positions Closed",
      description: `Closed ${positions.length} positions`,
    })
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold">Paper Trading</h2>
          <Badge variant="outline" className="text-[10px] bg-accent/10 text-accent border-accent/20">
            <CircleDot className="w-2 h-2 mr-1 animate-pulse" />
            Active
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8">
            <Settings className="w-3 h-3 mr-1" />
            Settings
          </Button>
          <NewOrderDialog onPlaceOrder={onPlaceOrder} positions={positions} />
        </div>
      </div>

      {/* Account Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Account Balance" value={formatCurrency(125847.32)} icon={<DollarSign className="w-4 h-4" />} />
        <StatCard 
          title="Unrealized PnL" 
          value={formatCurrency(unrealizedPnL)}
          trend={unrealizedPnL >= 0 ? 'up' : 'down'}
          icon={<TrendingUp className="w-4 h-4" />} 
        />
        <StatCard 
          title="Today's PnL" 
          value={formatCurrency(2834.56 + totalPnL)}
          trend="up"
          icon={<Activity className="w-4 h-4" />} 
        />
        <StatCard title="Margin Used" value="23.5%" icon={<Percent className="w-4 h-4" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Trading Panel */}
        <Card className="terminal-card bg-card/50 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Quick Trade</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <QuickTradePanel onPlaceOrder={onPlaceOrder} />
          </CardContent>
        </Card>

        {/* Open Positions */}
        <Card className="terminal-card bg-card/50 backdrop-blur-sm lg:col-span-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Open Positions</CardTitle>
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" className="h-6 text-xs">
                  <RefreshCw className="w-3 h-3" />
                </Button>
                {positions.length > 0 && (
                  <Button variant="ghost" size="sm" className="h-6 text-xs text-red-400" onClick={handleCloseAll}>
                    Close All
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground text-sm">
                No open positions. Place an order to start trading!
              </div>
            ) : (
              <div className="space-y-2">
                {positions.map((pos) => (
                  <div key={pos.id} className="flex items-center justify-between p-3 rounded bg-muted/20 hover:bg-muted/30 transition-colors">
                    <div className="flex items-center gap-3">
                      <Badge variant={pos.side === 'LONG' ? 'default' : 'destructive'} className="text-[10px]">
                        {pos.side}
                      </Badge>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono-data">{pos.symbol}</span>
                          <span className="text-[10px] text-muted-foreground">{pos.leverage}x</span>
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono-data">
                          Entry: ${pos.entry.toLocaleString()} • Size: {pos.size.toFixed(4)}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <div className={cn("text-sm font-mono-data", pos.pnl >= 0 ? "pnl-positive" : "pnl-negative")}>
                          {pos.pnl >= 0 ? '+' : ''}{formatCurrency(pos.pnl)}
                        </div>
                        <div className={cn("text-[10px]", pos.pnlPercent >= 0 ? "pnl-positive" : "pnl-negative")}>
                          {pos.pnlPercent >= 0 ? '+' : ''}{pos.pnlPercent.toFixed(2)}%
                        </div>
                      </div>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-7 text-xs text-red-400 hover:text-red-300"
                        onClick={() => handleClosePosition(pos.id)}
                      >
                        Close
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function QuickTradePanel({ onPlaceOrder }: { onPlaceOrder: (symbol: string, side: OrderSide, size: number, leverage: number) => void }) {
  const [symbol, setSymbol] = useState('BTC/USDT')
  const [side, setSide] = useState<OrderSide>('LONG')
  const [size, setSize] = useState('')
  const [leverage, setLeverage] = useState(1)
  const { toast } = useToast()

  const handlePlaceOrder = () => {
    const sizeNum = parseFloat(size)
    if (!sizeNum || sizeNum <= 0) {
      toast({
        title: "Invalid size",
        description: "Please enter a valid position size",
        variant: "destructive",
      })
      return
    }

    onPlaceOrder(symbol, side, sizeNum, leverage)
    toast({
      title: "Order Placed",
      description: `${side} $${sizeNum} ${symbol} at ${leverage}x leverage`,
    })
    setSize('')
  }

  const currentPrice = marketPrices[symbol]?.price || 0

  return (
    <>
      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Symbol</label>
        <Select value={symbol} onValueChange={setSymbol}>
          <SelectTrigger className="h-9 bg-muted/30 border-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.keys(marketPrices).map((s) => (
              <SelectItem key={s} value={s}>{s}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Button 
          variant={side === 'LONG' ? 'default' : 'outline'}
          className={cn(side === 'LONG' && "bg-green-600 hover:bg-green-700 text-white")}
          onClick={() => setSide('LONG')}
        >
          <TrendingUp className="w-3 h-3 mr-1" />
          Long
        </Button>
        <Button 
          variant={side === 'SHORT' ? 'default' : 'outline'}
          className={cn(side === 'SHORT' && "bg-red-600 hover:bg-red-700 text-white")}
          onClick={() => setSide('SHORT')}
        >
          <TrendingDown className="w-3 h-3 mr-1" />
          Short
        </Button>
      </div>
      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Size (USDT)</label>
        <Input 
          type="number" 
          placeholder="1000" 
          value={size}
          onChange={(e) => setSize(e.target.value)}
          className="h-9 bg-muted/30 border-0" 
        />
      </div>
      <div className="space-y-2">
        <label className="text-xs text-muted-foreground">Leverage</label>
        <div className="flex gap-1">
          {[1, 3, 5, 10, 20].map((lev) => (
            <Button 
              key={lev} 
              variant={leverage === lev ? 'default' : 'outline'}
              size="sm" 
              className={cn("h-7 text-xs flex-1", leverage === lev && "bg-accent text-accent-foreground")}
              onClick={() => setLeverage(lev)}
            >
              {lev}x
            </Button>
          ))}
        </div>
      </div>
      {size && (
        <div className="text-xs text-muted-foreground p-2 bg-muted/20 rounded">
          Entry: {formatCurrency(currentPrice)} • Qty: {(parseFloat(size) / currentPrice).toFixed(6)}
        </div>
      )}
      <Button className="w-full bg-accent text-accent-foreground hover:bg-accent/80" onClick={handlePlaceOrder}>
        Place Order
      </Button>
    </>
  )
}

function BacktestsView({ backtests, onCreateBacktest }: { backtests: Backtest[]; onCreateBacktest: (name: string, strategy: string) => void }) {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Backtests</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8">
            <Upload className="w-3 h-3 mr-1" />
            Import
          </Button>
          <NewBacktestDialog onCreateBacktest={onCreateBacktest} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {backtests.map((test) => (
          <Card key={test.id} className="terminal-card bg-card/50 backdrop-blur-sm">
            <CardContent className="p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="text-xs text-muted-foreground font-mono-data">{test.id}</div>
                  <div className="font-medium">{test.name}</div>
                </div>
                <Badge variant={test.status === 'completed' ? 'default' : test.status === 'running' ? 'secondary' : 'outline'} className="text-[10px]">
                  {test.status === 'running' && <RefreshCw className="w-2 h-2 mr-1 animate-spin" />}
                  {test.status}
                </Badge>
              </div>
              {test.status === 'completed' ? (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-[10px] text-muted-foreground">Return</div>
                    <div className="text-sm font-mono-data pnl-positive">+{test.return}%</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground">Sharpe</div>
                    <div className="text-sm font-mono-data">{test.sharpe}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground">Max DD</div>
                    <div className="text-sm font-mono-data pnl-negative">{test.maxDD}%</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-muted-foreground">Win Rate</div>
                    <div className="text-sm font-mono-data">{test.winRate}%</div>
                  </div>
                </div>
              ) : test.status === 'running' ? (
                <div className="space-y-2">
                  <Progress value={test.progress || 45} className="h-1" />
                  <div className="text-xs text-muted-foreground">Processing... {test.progress || 45}%</div>
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">Queued for execution</div>
              )}
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/30">
                <div className="text-[10px] text-muted-foreground">
                  {test.trades ? `${test.trades} trades` : '— trades'} • {test.created}
                </div>
                {test.status === 'completed' && <BacktestDetailsDialog backtest={test} />}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function ModelsView({ models, onTrainModel, onToggleModel }: { models: Model[]; onTrainModel: (name: string, type: Model['type']) => void; onToggleModel: (id: string) => void }) {
  const { toast } = useToast()

  const handleToggle = (id: string) => {
    onToggleModel(id)
    const model = models.find(m => m.id === id)
    toast({
      title: model?.status === 'active' ? "Model Deactivated" : "Model Activated",
      description: `${model?.name} has been ${model?.status === 'active' ? 'deactivated' : 'activated'}`,
    })
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">AI Models</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8">
            <GitBranch className="w-3 h-3 mr-1" />
            Compare
          </Button>
          <NewModelDialog onTrainModel={onTrainModel} />
        </div>
      </div>

      {/* Model Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Active Models" value={models.filter(m => m.status === 'active').length} icon={<Brain className="w-4 h-4" />} />
        <StatCard title="Avg Accuracy" value={`${(models.reduce((sum, m) => sum + m.accuracy, 0) / models.length).toFixed(1)}%`} icon={<Target className="w-4 h-4" />} />
        <StatCard title="Total Predictions" value={models.reduce((sum, m) => sum + m.predictions, 0).toLocaleString()} icon={<Zap className="w-4 h-4" />} />
        <StatCard title="Training Queue" value={models.filter(m => m.status === 'training').length} icon={<Cpu className="w-4 h-4" />} />
      </div>

      {/* Models Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {models.map((model) => (
          <Card key={model.id} className="terminal-card bg-card/50 backdrop-blur-sm">
            <CardContent className="p-4">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-accent/10">
                    <Brain className="w-5 h-5 text-accent" />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground font-mono-data">{model.id}</div>
                    <div className="font-medium">{model.name}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Switch 
                    checked={model.status === 'active'} 
                    onCheckedChange={() => handleToggle(model.id)}
                    disabled={model.status === 'training'}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-3 gap-4 mb-4">
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase">Type</div>
                  <div className="text-sm font-mono-data">{model.type}</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase">Accuracy</div>
                  <div className="text-sm font-mono-data text-accent">{model.accuracy}%</div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase">Predictions</div>
                  <div className="text-sm font-mono-data">{model.predictions.toLocaleString()}</div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-border/30">
                <div className="text-[10px] text-muted-foreground">
                  Last trained: {model.lastTrained}
                </div>
                <div className="flex gap-1">
                  <ModelDetailsDialog model={model} />
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-6 text-xs"
                    disabled={model.status === 'training'}
                  >
                    Retrain
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function DatabaseView() {
  const [query, setQuery] = useState(`SELECT * FROM ohlcv_1m
WHERE symbol = 'BTC/USDT'
ORDER BY timestamp DESC
LIMIT 100;`)
  const [queryResult, setQueryResult] = useState<string | null>(null)
  const { toast } = useToast()

  const handleExecuteQuery = () => {
    toast({
      title: "Query Executed",
      description: "Query returned 100 rows",
    })
    setQueryResult(`100 rows returned in 23ms

| timestamp           | symbol    | open    | high    | low     | close   | volume   |
|---------------------|-----------|---------|---------|---------|---------|----------|
| 2024-01-15 14:32:00 | BTC/USDT  | 67800.5 | 67850.0 | 67750.0 | 67842.5 | 125.4    |
| 2024-01-15 14:31:00 | BTC/USDT  | 67750.0 | 67810.0 | 67720.0 | 67800.5 | 98.2     |
| 2024-01-15 14:30:00 | BTC/USDT  | 67700.0 | 67780.0 | 67690.0 | 67750.0 | 142.7    |
...`)
  }

  const handleExport = (table: string) => {
    toast({
      title: "Export Started",
      description: `Exporting ${table} data...`,
    })
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Database</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8">
            <Download className="w-3 h-3 mr-1" />
            Export All
          </Button>
          <Button variant="outline" size="sm" className="h-8">
            <RefreshCw className="w-3 h-3 mr-1" />
            Sync
          </Button>
        </div>
      </div>

      {/* DB Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Tables" value="6" icon={<Database className="w-4 h-4" />} />
        <StatCard title="Total Rows" value="3.1M" icon={<Layers className="w-4 h-4" />} />
        <StatCard title="Storage Used" value="1.6 GB" icon={<HardDrive className="w-4 h-4" />} />
        <StatCard title="Last Sync" value="2s ago" icon={<Clock className="w-4 h-4" />} />
      </div>

      {/* Tables */}
      <Card className="terminal-card bg-card/50 backdrop-blur-sm">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="text-left p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Table Name</th>
                  <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Rows</th>
                  <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Size</th>
                  <th className="text-right p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Last Update</th>
                  <th className="text-center p-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {dbTables.map((table, i) => (
                  <tr key={i} className="border-b border-border/30 hover:bg-muted/20 transition-colors">
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <Database className="w-4 h-4 text-muted-foreground" />
                        <span className="font-mono-data text-sm">{table.name}</span>
                      </div>
                    </td>
                    <td className="p-3 text-right font-mono-data text-muted-foreground">
                      {table.rows.toLocaleString()}
                    </td>
                    <td className="p-3 text-right font-mono-data text-muted-foreground">
                      {table.size}
                    </td>
                    <td className="p-3 text-right text-xs text-muted-foreground">
                      {table.lastUpdate}
                    </td>
                    <td className="p-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={handleExecuteQuery}>Query</Button>
                        <Button variant="ghost" size="sm" className="h-7 text-xs text-accent" onClick={() => handleExport(table.name)}>Export</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Query Console */}
      <Card className="terminal-card bg-card/50 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Terminal className="w-4 h-4 text-accent" />
              Query Console
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => setQuery('')}>
                Clear
              </Button>
              <Button size="sm" className="h-7 text-xs bg-accent text-accent-foreground" onClick={handleExecuteQuery}>
                <Play className="w-3 h-3 mr-1" />
                Execute
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="font-mono text-xs bg-muted/30 border-0 min-h-24"
            placeholder="Enter SQL query..."
          />
          {queryResult && (
            <div className="mt-3 p-3 rounded bg-muted/20 font-mono text-xs whitespace-pre-wrap">
              {queryResult}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// Main Page Component
export default function Home() {
  const [activeView, setActiveView] = useState<NavItem>('overview')
  const [positions, setPositions] = useState<Position[]>([
    { id: '1', symbol: 'BTC/USDT', side: 'LONG', entry: 66800, current: 67842, size: 0.5, pnl: 521, pnlPercent: 1.56, leverage: 5, timestamp: new Date() },
    { id: '2', symbol: 'ETH/USDT', side: 'SHORT', entry: 3520, current: 3456, size: 2.0, pnl: 128, pnlPercent: 1.82, leverage: 3, timestamp: new Date() },
    { id: '3', symbol: 'SOL/USDT', side: 'LONG', entry: 168, current: 178, size: 15, pnl: 150, pnlPercent: 5.95, leverage: 2, timestamp: new Date() },
  ])
  const [trades, setTrades] = useState<Trade[]>([
    { id: '1', time: '14:32:15', symbol: 'BTC/USDT', side: 'BUY', price: 67800, size: 0.25, pnl: null, timestamp: new Date() },
    { id: '2', time: '14:28:42', symbol: 'ETH/USDT', side: 'SELL', price: 3460, size: 1.5, pnl: 45.23, timestamp: new Date() },
    { id: '3', time: '14:15:08', symbol: 'SOL/USDT', side: 'BUY', price: 175, size: 10, pnl: null, timestamp: new Date() },
    { id: '4', time: '13:58:33', symbol: 'BTC/USDT', side: 'SELL', price: 67650, size: 0.15, pnl: -23.50, timestamp: new Date() },
    { id: '5', time: '13:42:19', symbol: 'AVAX/USDT', side: 'BUY', price: 38.50, size: 25, pnl: null, timestamp: new Date() },
  ])
  const [backtests, setBacktests] = useState<Backtest[]>([
    { id: 'BT-001', name: 'BTC Trend Following', status: 'completed', return: 45.2, sharpe: 2.1, maxDD: -12.3, winRate: 58.4, trades: 234, created: '2024-01-15' },
    { id: 'BT-002', name: 'ETH Mean Reversion', status: 'completed', return: 32.8, sharpe: 1.8, maxDD: -8.9, winRate: 62.1, trades: 156, created: '2024-01-14' },
    { id: 'BT-003', name: 'Multi-Asset Momentum', status: 'running', return: null, sharpe: null, maxDD: null, winRate: null, trades: null, created: '2024-01-15', progress: 45 },
    { id: 'BT-004', name: 'Grid Trading Bot', status: 'queued', return: null, sharpe: null, maxDD: null, winRate: null, trades: null, created: '2024-01-15' },
  ])
  const [models, setModels] = useState<Model[]>([
    { id: 'M-001', name: 'LSTM Predictor v2', type: 'LSTM', accuracy: 67.8, lastTrained: '2h ago', status: 'active', predictions: 15234 },
    { id: 'M-002', name: 'Transformer Price', type: 'Transformer', accuracy: 71.2, lastTrained: '1d ago', status: 'active', predictions: 8921 },
    { id: 'M-003', name: 'XGBoost Classifier', type: 'XGBoost', accuracy: 64.5, lastTrained: '4h ago', status: 'active', predictions: 23156 },
    { id: 'M-004', name: 'Ensemble Meta', type: 'Ensemble', accuracy: 73.4, lastTrained: '6h ago', status: 'training', predictions: 0 },
  ])

  const { toast } = useToast()

  // Handlers
  const handlePlaceOrder = useCallback((symbol: string, side: OrderSide, size: number, leverage: number) => {
    const price = marketPrices[symbol]?.price || 0
    const quantity = size / price
    
    // Simulate slight price movement for PnL
    const priceChange = (Math.random() - 0.5) * price * 0.001
    const newPrice = side === 'LONG' ? price + priceChange : price - priceChange
    const pnl = side === 'LONG' 
      ? (newPrice - price) * quantity * leverage 
      : (price - newPrice) * quantity * leverage
    const pnlPercent = (pnl / size) * 100

    const newPosition: Position = {
      id: generateId(),
      symbol,
      side,
      entry: price,
      current: newPrice,
      size: quantity,
      pnl,
      pnlPercent,
      leverage,
      timestamp: new Date()
    }

    const newTrade: Trade = {
      id: generateId(),
      time: formatTime(new Date()),
      symbol,
      side: side === 'LONG' ? 'BUY' : 'SELL',
      price,
      size: quantity,
      pnl: null,
      timestamp: new Date()
    }

    setPositions(prev => [newPosition, ...prev])
    setTrades(prev => [newTrade, ...prev])
  }, [])

  const handleClosePosition = useCallback((id: string) => {
    const position = positions.find(p => p.id === id)
    if (position) {
      const closeTrade: Trade = {
        id: generateId(),
        time: formatTime(new Date()),
        symbol: position.symbol,
        side: position.side === 'LONG' ? 'SELL' : 'BUY',
        price: position.current,
        size: position.size,
        pnl: position.pnl,
        timestamp: new Date()
      }
      setTrades(prev => [closeTrade, ...prev])
      setPositions(prev => prev.filter(p => p.id !== id))
    }
  }, [positions])

  const handleCloseAllPositions = useCallback(() => {
    positions.forEach(pos => {
      const closeTrade: Trade = {
        id: generateId(),
        time: formatTime(new Date()),
        symbol: pos.symbol,
        side: pos.side === 'LONG' ? 'SELL' : 'BUY',
        price: pos.current,
        size: pos.size,
        pnl: pos.pnl,
        timestamp: new Date()
      }
      setTrades(prev => [closeTrade, ...prev])
    })
    setPositions([])
  }, [positions])

  const handleCreateBacktest = useCallback((name: string, strategy: string) => {
    const newBacktest: Backtest = {
      id: `BT-${String(backtests.length + 1).padStart(3, '0')}`,
      name,
      status: 'queued',
      return: null,
      sharpe: null,
      maxDD: null,
      winRate: null,
      trades: null,
      created: new Date().toISOString().split('T')[0]
    }
    setBacktests(prev => [newBacktest, ...prev])
  }, [backtests.length])

  const handleTrainModel = useCallback((name: string, type: Model['type']) => {
    const newModel: Model = {
      id: `M-${String(models.length + 1).padStart(3, '0')}`,
      name,
      type,
      accuracy: 0,
      lastTrained: 'Just now',
      status: 'training',
      predictions: 0
    }
    setModels(prev => [newModel, ...prev])
  }, [models.length])

  const handleToggleModel = useCallback((id: string) => {
    setModels(prev => prev.map(m => 
      m.id === id ? { ...m, status: m.status === 'active' ? 'inactive' : 'active' } : m
    ))
  }, [])

  const handleTradeSymbol = useCallback((symbol: string) => {
    setActiveView('paper-trading')
    toast({
      title: "Ready to Trade",
      description: `Select ${symbol} in the trading panel`,
    })
  }, [toast])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Left Navigation Panel */}
      <aside className="w-56 bg-sidebar border-r border-sidebar-border flex flex-col shrink-0">
        {/* Logo/Title */}
        <div className="p-4 border-b border-sidebar-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-accent" />
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-tight">MarketPy</h1>
              <p className="text-[10px] text-muted-foreground -mt-0.5">Trading Simulator</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1">
          <NavLink 
            icon={<LayoutDashboard className="w-4 h-4" />}
            label="Overview"
            active={activeView === 'overview'}
            onClick={() => setActiveView('overview')}
          />
          <NavLink 
            icon={<TrendingUp className="w-4 h-4" />}
            label="Markets"
            active={activeView === 'markets'}
            onClick={() => setActiveView('markets')}
            badge={Object.keys(marketPrices).length.toString()}
          />
          <NavLink 
            icon={<FlaskConical className="w-4 h-4" />}
            label="Paper Trading"
            active={activeView === 'paper-trading'}
            onClick={() => setActiveView('paper-trading')}
            badge={positions.length > 0 ? positions.length.toString() : undefined}
          />
          <NavLink 
            icon={<History className="w-4 h-4" />}
            label="Backtests"
            active={activeView === 'backtests'}
            onClick={() => setActiveView('backtests')}
            badge={backtests.filter(b => b.status === 'running' || b.status === 'queued').length > 0 
              ? backtests.filter(b => b.status === 'running' || b.status === 'queued').length.toString() 
              : undefined}
          />
          <NavLink 
            icon={<Brain className="w-4 h-4" />}
            label="Models"
            active={activeView === 'models'}
            onClick={() => setActiveView('models')}
          />
          <NavLink 
            icon={<Database className="w-4 h-4" />}
            label="Database"
            active={activeView === 'database'}
            onClick={() => setActiveView('database')}
          />
        </nav>

        {/* Status Area */}
        <div className="p-3 border-t border-sidebar-border space-y-3">
          {/* Connection Status */}
          <div className="p-2 rounded bg-muted/30 space-y-2">
            <div className="flex items-center justify-between">
              <StatusIndicator status="connected" label="Connected" />
              <Badge variant="outline" className="text-[10px] bg-accent/5 border-accent/20 text-accent">
                Paper
              </Badge>
            </div>
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <span>API Latency</span>
              <span className="font-mono-data text-accent">23ms</span>
            </div>
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <span>Last Update</span>
              <span className="font-mono-data">2s ago</span>
            </div>
          </div>

          {/* User Profile */}
          <div className="flex items-center gap-2 p-2 rounded hover:bg-muted/30 cursor-pointer transition-colors">
            <div className="w-7 h-7 rounded-full bg-accent/10 flex items-center justify-center">
              <span className="text-xs font-bold text-accent">JP</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate">John Pro</div>
              <div className="text-[10px] text-muted-foreground">Pro Plan</div>
            </div>
            <Settings className="w-3.5 h-3.5 text-muted-foreground" />
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-12 border-b border-border flex items-center justify-between px-4 shrink-0 bg-card/30 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1 text-xs">
              <span className="text-muted-foreground">MarketPy</span>
              <ChevronRight className="w-3 h-3 text-muted-foreground" />
              <span className="font-medium capitalize">{activeView.replace('-', ' ')}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
              <Bell className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
              <Settings className="w-4 h-4" />
            </Button>
          </div>
        </header>

        {/* Content Area */}
        <ScrollArea className="flex-1">
          <div className="p-6">
            {activeView === 'overview' && (
              <OverviewView 
                positions={positions} 
                trades={trades} 
                onTradeClick={() => setActiveView('paper-trading')}
              />
            )}
            {activeView === 'markets' && (
              <MarketsView onTradeSymbol={handleTradeSymbol} />
            )}
            {activeView === 'paper-trading' && (
              <PaperTradingView 
                positions={positions}
                trades={trades}
                onPlaceOrder={handlePlaceOrder}
                onClosePosition={handleClosePosition}
                onCloseAllPositions={handleCloseAllPositions}
              />
            )}
            {activeView === 'backtests' && (
              <BacktestsView backtests={backtests} onCreateBacktest={handleCreateBacktest} />
            )}
            {activeView === 'models' && (
              <ModelsView models={models} onTrainModel={handleTrainModel} onToggleModel={handleToggleModel} />
            )}
            {activeView === 'database' && <DatabaseView />}
          </div>
        </ScrollArea>
      </main>
    </div>
  )
}
