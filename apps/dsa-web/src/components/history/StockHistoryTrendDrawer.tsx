import type React from 'react';
import { useMemo } from 'react';
import type { AnalysisReport, HistoryItem, StockHistoryFilters, StockHistoryRange } from '../../types/analysis';
import { getSentimentColor } from '../../types/analysis';
import { formatDateTime, formatReportType } from '../../utils/format';
import { Badge, Button, Drawer } from '../common';
import { DashboardStateBlock } from '../dashboard';

interface StockHistoryTrendDrawerProps {
  report: AnalysisReport;
  items: HistoryItem[];
  total: number;
  hasMore: boolean;
  isLoading: boolean;
  isLoadingMore: boolean;
  error?: unknown;
  filters: StockHistoryFilters;
  onClose: () => void;
  onRangeChange: (range: StockHistoryRange) => void;
  onLoadMore: () => void;
  onSelectRecord: (recordId: number) => void;
  onRetry: () => void;
}

const RANGE_OPTIONS: Array<{ value: StockHistoryRange; label: string }> = [
  { value: 'all', label: '全部历史' },
  { value: '30d', label: '近30天' },
  { value: '90d', label: '近90天' },
];

const isPresent = <T,>(value: T | null | undefined): value is T =>
  value !== undefined && value !== null && value !== '';

const formatNumber = (value?: number, digits = 2): string =>
  typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '--';

const formatChangePct = (value?: number): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '--';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
};

const formatAdvice = (item: HistoryItem): string => {
  const advice = item.operationAdvice?.trim();
  const trend = item.trendPrediction?.trim();
  if (advice && trend) {
    return `${advice} / ${trend}`;
  }
  return advice || trend || '--';
};

const summarizeView = (items: HistoryItem[], currentId?: number) => {
  const scores = items
    .map((item) => item.sentimentScore)
    .filter((score): score is number => typeof score === 'number' && Number.isFinite(score));
  const current = items.find((item) => item.id === currentId) || items[0];
  const latestScore = current?.sentimentScore;
  const averageScore = scores.length
    ? scores.reduce((sum, score) => sum + score, 0) / scores.length
    : undefined;
  const scoreTrail = scores.slice(0, 6).reverse();
  const models = new Map<string, number>();
  items.forEach((item) => {
    const model = item.modelUsed?.trim();
    if (model) {
      models.set(model, (models.get(model) || 0) + 1);
    }
  });

  return {
    current,
    latestScore,
    averageScore,
    scoreTrail,
    modelSummary: Array.from(models.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([model, count]) => `${model} ${count}次`)
      .join(' / '),
  };
};

export const StockHistoryTrendDrawer: React.FC<StockHistoryTrendDrawerProps> = ({
  report,
  items,
  total,
  hasMore,
  isLoading,
  isLoadingMore,
  error,
  filters,
  onClose,
  onRangeChange,
  onLoadMore,
  onSelectRecord,
  onRetry,
}) => {
  const currentRecordId = report.meta.id;
  const stockLabel = `${report.meta.stockName || report.meta.stockCode} ${report.meta.stockCode}`;
  const summary = useMemo(() => summarizeView(items, currentRecordId), [currentRecordId, items]);
  const currentModel = report.meta.modelUsed || summary.current?.modelUsed || '--';
  const currentAdvice = summary.current
    ? formatAdvice(summary.current)
    : formatAdvice({
        id: 0,
        queryId: report.meta.queryId,
        stockCode: report.meta.stockCode,
        createdAt: report.meta.createdAt,
        operationAdvice: report.summary.operationAdvice,
        trendPrediction: report.summary.trendPrediction,
      });

  return (
    <Drawer
      isOpen
      onClose={onClose}
      title="同股历史趋势"
      width="max-w-3xl"
      zIndex={90}
      backdropClassName="bg-background/50 backdrop-blur-[2px]"
    >
      <div className="space-y-4">
        <section className="rounded-2xl border border-border/70 bg-card/90 p-4 shadow-soft-card">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-secondary-text">
                Stock Timeline
              </p>
              <h3 className="mt-1 text-xl font-semibold text-foreground">{stockLabel}</h3>
              <p className="mt-1 text-sm text-secondary-text">
                共 {total || items.length} 次分析 · 最近 {formatDateTime(items[0]?.createdAt || report.meta.createdAt)}
              </p>
            </div>
            <Badge variant="info" size="sm" className="shadow-none">
              当前 {currentAdvice}
            </Badge>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border/60 bg-background/70 p-3">
              <p className="text-xs text-secondary-text">当前分数</p>
              <p className="mt-1 font-mono text-2xl font-semibold text-foreground">
                {formatNumber(summary.latestScore, 0)}
              </p>
            </div>
            <div className="rounded-xl border border-border/60 bg-background/70 p-3">
              <p className="text-xs text-secondary-text">平均分</p>
              <p className="mt-1 font-mono text-2xl font-semibold text-foreground">
                {formatNumber(summary.averageScore, 1)}
              </p>
            </div>
            <div className="rounded-xl border border-border/60 bg-background/70 p-3">
              <p className="text-xs text-secondary-text">当前模型</p>
              <p className="mt-1 truncate text-sm font-semibold text-foreground" title={currentModel}>
                {currentModel}
              </p>
            </div>
          </div>

          {summary.scoreTrail.length >= 2 ? (
            <div className="mt-4 rounded-xl border border-border/60 bg-background/70 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-secondary-text">分数走势</span>
                {summary.scoreTrail.map((score, index) => (
                  <span key={`${score}-${index}`} className="flex items-center gap-2">
                    {index > 0 && <span className="text-muted-text">→</span>}
                    <span
                      className="rounded-full border px-2 py-0.5 font-mono text-xs font-semibold"
                      style={{
                        color: getSentimentColor(score),
                        borderColor: `${getSentimentColor(score)}40`,
                        backgroundColor: `${getSentimentColor(score)}12`,
                      }}
                    >
                      {score}
                    </span>
                  </span>
                ))}
              </div>
              {summary.modelSummary ? (
                <p className="mt-2 text-xs text-secondary-text">模型分布：{summary.modelSummary}</p>
              ) : null}
            </div>
          ) : (
            <p className="mt-4 rounded-xl border border-dashed border-border/70 bg-background/60 px-3 py-2 text-sm text-secondary-text">
              当前历史记录不足，暂无法形成趋势。
            </p>
          )}
        </section>

        <section className="rounded-2xl border border-border/70 bg-card/90 p-4 shadow-soft-card">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              {RANGE_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onRangeChange(option.value)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    filters.range === option.value
                      ? 'border-primary/50 bg-primary/10 text-primary'
                      : 'border-border/70 bg-background/70 text-secondary-text hover:bg-hover hover:text-foreground'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 text-xs text-secondary-text">
              <span>模型：全部</span>
              <span>最新优先</span>
            </div>
          </div>
        </section>

        {isLoading ? (
          <DashboardStateBlock loading compact title="加载同股历史中..." />
        ) : error ? (
          <DashboardStateBlock
            compact
            title="历史趋势加载失败"
            description="请稍后重试"
            action={(
              <Button variant="secondary" size="sm" onClick={onRetry}>
                重新加载
              </Button>
            )}
          />
        ) : items.length === 0 ? (
          <DashboardStateBlock
            compact
            title="暂无更多同股历史分析"
            description="完成多次分析后，这里会展示观点变化、评分走势和模型记录。"
          />
        ) : (
          <section className="space-y-3">
            {items.map((item) => {
              const isCurrent = item.id === currentRecordId;
              const sentimentColor = isPresent(item.sentimentScore)
                ? getSentimentColor(item.sentimentScore)
                : undefined;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectRecord(item.id)}
                  className={`w-full rounded-2xl border p-4 text-left shadow-soft-card transition-colors ${
                    isCurrent
                      ? 'border-primary/45 bg-primary/10'
                      : 'border-border/70 bg-card/90 hover:border-primary/30 hover:bg-hover/60'
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-secondary-text">
                          {formatDateTime(item.createdAt)}
                        </span>
                        {isCurrent && (
                          <Badge variant="info" size="sm" className="shadow-none">
                            当前
                          </Badge>
                        )}
                        {item.reportType && (
                          <Badge variant="default" size="sm" className="shadow-none">
                            {formatReportType(item.reportType)}
                          </Badge>
                        )}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-foreground">{formatAdvice(item)}</span>
                        {isPresent(item.sentimentScore) && sentimentColor && (
                          <span
                            className="rounded-full border px-2 py-0.5 font-mono text-xs font-semibold"
                            style={{
                              color: sentimentColor,
                              borderColor: `${sentimentColor}40`,
                              backgroundColor: `${sentimentColor}12`,
                            }}
                          >
                            {item.sentimentScore}
                          </span>
                        )}
                        <span className="font-mono text-xs text-secondary-text">
                          {formatChangePct(item.changePct)}
                        </span>
                      </div>
                      <p className="mt-2 line-clamp-2 text-sm leading-6 text-secondary-text">
                        {item.analysisSummary || '暂无分析摘要'}
                      </p>
                    </div>
                    <div className="w-full shrink-0 text-left sm:w-44 sm:text-right">
                      <p className="truncate text-xs font-medium text-foreground" title={item.modelUsed || undefined}>
                        {item.modelUsed || '--'}
                      </p>
                      <p className="mt-1 font-mono text-xs text-secondary-text">
                        价格 {formatNumber(item.currentPrice, 2)}
                      </p>
                    </div>
                  </div>
                </button>
              );
            })}

            <div className="flex flex-col items-center gap-2 pt-2">
              <p className="text-xs text-secondary-text">
                已加载 {items.length} / {total || items.length} 条
              </p>
              {hasMore && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={onLoadMore}
                  isLoading={isLoadingMore}
                  loadingText="加载中..."
                >
                  加载更多
                </Button>
              )}
            </div>
          </section>
        )}
      </div>
    </Drawer>
  );
};
