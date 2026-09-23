import { Select } from 'antd';
import type { AnalysisRun } from '../api/demo';

export function AnalysisHistory({
  runs,
  selectedRunId,
  busy,
  onSelect,
}: {
  runs: AnalysisRun[];
  selectedRunId?: string;
  busy: boolean;
  onSelect: (runId: string) => void;
}) {
  if (!runs.length) return null;

  return (
    <div className="analysis-history">
      <span>展示记录</span>
      <Select
        aria-label="分析历史"
        value={selectedRunId}
        loading={busy}
        disabled={busy}
        placeholder="选择一次成功分析"
        onChange={onSelect}
        options={runs.map((run) => ({
          value: run.id,
          disabled: run.status !== 'completed',
          label: `第 ${run.attempt} 次 · ${
            run.status === 'completed'
              ? '分析成功'
              : run.status === 'failed'
                ? '分析失败'
                : '进行中'
          }${run.selected ? ' · 当前展示' : ''}`,
        }))}
      />
    </div>
  );
}
