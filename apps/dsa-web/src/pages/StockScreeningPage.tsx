import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CircleAlert, Play, PlusCircle, Search, SlidersHorizontal } from 'lucide-react';
import { alphasiftApi, type AlphaSiftCandidate } from '../api/alphasift';
import { AppPage, Button, InlineAlert } from '../components/common';

const STRATEGIES = [
  {
    id: 'balanced_alpha',
    title: '均衡多因子',
    description: '综合估值、资金、动量、稳定性的通用候选发现策略',
    tag: '框架',
  },
  {
    id: 'capital_heat',
    title: '资金热度',
    description: '资金活跃、量价同步但未被透支的短线候选',
    tag: '动量',
  },
  {
    id: 'dual_low',
    title: '双低选股',
    description: '偏稳健的低估值筛选策略，适合价值投资者',
    tag: '价值',
  },
  {
    id: 'trend_quality',
    title: '趋势质量',
    description: '兼顾趋势确认和基本面质量的中线候选发现',
    tag: '框架',
  },
  {
    id: 'oversold_reversal',
    title: '超跌反转',
    description: '跌幅可控、流动性仍在、具备修复观察价值的反转候选',
    tag: '反转',
  },
  {
    id: 'stable_value',
    title: '稳健价值',
    description: '估值合理、流动性充足、波动不过热的稳健候选',
    tag: '价值',
  },
  {
    id: 'shrink_pullback',
    title: '缩量回踩',
    description: '上升趋势中缩量回踩支撑，观察趋势延续的入场信号',
    tag: '趋势',
  },
  {
    id: 'volume_breakout',
    title: '放量突破',
    description: '成交量放大突破关键阻力位，趋势启动信号',
    tag: '趋势',
  },
];

const MARKETS = [
  { id: 'cn', label: 'A 股' },
];

const getCandidateReason = (item: AlphaSiftCandidate) => {
  if (item.reason) {
    return item.reason;
  }

  const rawReason = item.raw.reason ?? item.raw.summary ?? item.raw.analysis;
  return typeof rawReason === 'string' ? rawReason : 'AlphaSift 返回候选，暂无摘要。';
};

const getSignal = (item: AlphaSiftCandidate) => {
  const rawSignal = item.raw.action ?? item.raw.signal ?? item.raw.recommendation;
  return typeof rawSignal === 'string' && rawSignal.trim() ? rawSignal : '观察';
};

const formatScore = (score: AlphaSiftCandidate['score']) => {
  if (score == null || Number.isNaN(Number(score))) {
    return '-';
  }
  return Number(score).toFixed(2);
};

const StockScreeningPage: React.FC = () => {
  const [enabled, setEnabled] = useState(false);
  const [market, setMarket] = useState('cn');
  const [strategy, setStrategy] = useState('dual_low');
  const [maxResults, setMaxResults] = useState(20);
  const [candidates, setCandidates] = useState<AlphaSiftCandidate[]>([]);
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [enabling, setEnabling] = useState(false);
  const [error, setError] = useState('');

  const selectedStrategy = useMemo(() => STRATEGIES.find((item) => item.id === strategy), [strategy]);
  const selectedStrategyTitle = selectedStrategy?.title ?? '自定义策略';
  const selectedStrategyTag = selectedStrategy?.tag ?? '自定义';
  const displayedStrategy = selectedStrategy ? selectedStrategyTitle : `自定义策略（${strategy}）`;

  useEffect(() => {
    alphasiftApi
      .getStatus()
      .then((status) => setEnabled(status.enabled))
      .catch(() => setEnabled(false));
  }, []);

  const handleEnable = async () => {
    setEnabling(true);
    setError('');
    try {
      await alphasiftApi.enable();
      setEnabled(true);
    } catch (err) {
      try {
        const status = await alphasiftApi.getStatus();
        setEnabled(status.enabled);
      } catch {
        setEnabled(false);
      }
      setError(err instanceof Error ? err.message : '开启 AlphaSift 失败');
    } finally {
      setEnabling(false);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await alphasiftApi.screen({ market, strategy, maxResults });
      setCandidates(result.candidates);
      setExpandedCode(result.candidates[0]?.code ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : '选股失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppPage className="max-w-6xl space-y-6 pb-12 pt-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="grid h-7 w-7 place-items-center rounded-full border-2 border-cyan text-cyan shadow-[0_0_24px_hsl(var(--primary)/0.18)]">
            <PlusCircle className="h-4 w-4" />
          </span>
          <div>
            <h1 className="text-2xl font-bold tracking-normal text-foreground">AlphaSift 选股</h1>
            <p className="mt-1 text-sm text-secondary-text">开启后调用本地 alphasift.screen() 生成候选股票</p>
          </div>
        </div>

        <div className="inline-flex w-fit items-center gap-2 rounded-2xl border border-border/70 bg-card/80 px-4 py-2 text-sm shadow-soft-card">
          <span className={`h-2.5 w-2.5 rounded-full ${enabled ? 'bg-success' : 'bg-warning'}`} />
          <span className="font-medium text-secondary-text">{enabled ? '选股已开启' : '选股未开启'}</span>
        </div>
      </div>

      {!enabled ? (
        <InlineAlert
          variant="info"
          title="AlphaSift 未开启"
          message="点击后写入 ALPHASIFT_ENABLED=true，自动检查并安装 AlphaSift 依赖；也可以在设置页或 .env 中配置。"
          action={
            <Button size="sm" isLoading={enabling} loadingText="开启中..." onClick={() => void handleEnable()}>
              开启 AlphaSift
            </Button>
          }
        />
      ) : null}

      <InlineAlert
        variant="warning"
        title="风险提示"
        message="AlphaSift 选股结果仅用于研究和辅助判断，不构成投资建议；市场有风险，交易决策和损益由使用者自行承担。"
      />

      {error ? <InlineAlert variant="danger" title="调用失败" message={error} /> : null}

      <section className="rounded-2xl border border-cyan/35 bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">选择策略</h2>
            <p className="mt-1 text-xs text-secondary-text">策略会作为参数直接传给 AlphaSift，可按需切换或手动输入。</p>
          </div>
          <span className="rounded-full border border-cyan/30 bg-cyan/10 px-3 py-1 text-xs font-semibold text-cyan">
            {selectedStrategyTag}
          </span>
        </div>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {STRATEGIES.map((item) => {
            const selected = item.id === strategy;
            return (
              <button
                key={item.id}
                className={`min-h-28 rounded-xl border p-4 text-left transition-all ${
                  selected
                    ? 'border-cyan bg-cyan/10 shadow-[0_0_0_1px_hsl(var(--primary)/0.15),0_16px_36px_hsl(var(--primary)/0.12)]'
                    : 'border-border/80 bg-surface/70 hover:border-cyan/45 hover:bg-hover/70'
                }`}
                type="button"
                onClick={() => setStrategy(item.id)}
              >
                <span className="text-base font-semibold text-foreground">{item.title}</span>
                <span className="mt-2 block text-sm leading-6 text-secondary-text">{item.description}</span>
                <span className="mt-3 inline-flex text-xs font-semibold text-cyan">{item.tag}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-foreground">
          <SlidersHorizontal className="h-4 w-4 text-cyan" />
          参数设置
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr_180px_auto] lg:items-end">
          <label className="space-y-2 text-xs font-medium text-secondary-text">
            市场
            <select
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              value={market}
              onChange={(event) => setMarket(event.target.value)}
            >
              {MARKETS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2 text-xs font-medium text-secondary-text">
            策略参数
            <input
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              value={strategy}
              onChange={(event) => setStrategy(event.target.value)}
            />
          </label>

          <label className="space-y-2 text-xs font-medium text-secondary-text">
            返回数量
            <input
              className="h-11 w-full rounded-xl border border-border bg-surface px-3 text-sm text-foreground outline-none transition-colors focus:border-cyan"
              type="number"
              min={1}
              max={100}
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
            />
          </label>

          <Button
            className="h-11 min-w-40"
            isLoading={loading}
            loadingText="筛选中..."
            disabled={!enabled || loading}
            onClick={() => void handleSubmit()}
          >
            <Play className="h-4 w-4" />
            运行选股
          </Button>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span
              className={`grid h-7 w-7 place-items-center rounded-full ${
                candidates.length > 0 ? 'text-success' : enabled ? 'text-cyan' : 'text-warning'
              }`}
            >
              {candidates.length > 0 ? <CheckCircle2 className="h-5 w-5" /> : <CircleAlert className="h-5 w-5" />}
            </span>
            <div>
              <h2 className="text-sm font-semibold text-foreground">
                {candidates.length > 0 ? '选股完成' : enabled ? '等待运行' : '等待开启'}
              </h2>
              <p className="mt-1 text-xs text-secondary-text">
                当前策略：{displayedStrategy} · {MARKETS.find((item) => item.id === market)?.label}
              </p>
            </div>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-border sm:w-36">
            <div
              className={`h-full rounded-full transition-all ${
                loading ? 'w-2/3 animate-pulse bg-cyan' : candidates.length > 0 ? 'w-full bg-cyan' : 'w-1/4 bg-border'
              }`}
            />
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/95 p-4 shadow-soft-card">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">选股结果</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary-text">
              AlphaSift 返回的候选会在这里展示，首条结果默认展开，便于快速查看分数、建议和判断依据。
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-2 text-xs text-secondary-text">
            <Search className="h-4 w-4 text-cyan" />
            {candidates.length} 条候选
          </div>
        </div>

        {candidates.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border bg-surface/70 px-5 py-10 text-center">
            <p className="text-sm font-medium text-foreground">暂无结果</p>
            <p className="mt-2 text-sm text-secondary-text">开启 AlphaSift 后点击“运行选股”生成候选列表。</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            <table className="w-full min-w-[760px] border-collapse text-sm">
              <thead className="bg-surface text-left text-xs text-secondary-text">
                <tr>
                  <th className="w-14 px-4 py-3 font-semibold">#</th>
                  <th className="px-4 py-3 font-semibold">代码</th>
                  <th className="px-4 py-3 font-semibold">名称</th>
                  <th className="px-4 py-3 font-semibold">评分 DSA</th>
                  <th className="px-4 py-3 font-semibold">操作建议</th>
                  <th className="px-4 py-3 font-semibold">说明</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((item) => {
                  const expanded = expandedCode === item.code;
                  return (
                    <tr
                      key={`${item.rank}-${item.code}`}
                      className="border-t border-border align-top transition-colors hover:bg-hover/50"
                    >
                      <td className="px-4 py-3 text-secondary-text">{item.rank}</td>
                      <td className="px-4 py-3 font-mono font-semibold text-foreground">{item.code}</td>
                      <td className="px-4 py-3 font-semibold text-foreground">{item.name || '-'}</td>
                      <td className="px-4 py-3 font-bold text-cyan">{formatScore(item.score)}</td>
                      <td className="px-4 py-3">
                        <span className="rounded-lg bg-success/10 px-2.5 py-1 text-xs font-semibold text-success">
                          {getSignal(item)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          className="text-left text-sm text-secondary-text transition-colors hover:text-foreground"
                          type="button"
                          onClick={() => setExpandedCode(expanded ? null : item.code)}
                        >
                          {expanded ? getCandidateReason(item) : '展开查看'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </AppPage>
  );
};

export default StockScreeningPage;
