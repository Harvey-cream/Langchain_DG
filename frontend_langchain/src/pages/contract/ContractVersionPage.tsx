import { useEffect, useState } from 'react';
import { Alert, Button, Empty, Select, Spin, Tag, Upload, message } from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { listContractVersions } from '../../features/contract/api';
import {
  getContract,
  listAnalysisRuns,
  selectAnalysisRun,
  uploadContract,
  retryAnalysis,
  errorText,
} from '../../features/contract/api/demo';
import type { AnalysisRun } from '../../features/contract/api/demo';
import { useContractAnalysis } from '../../features/contract/hooks/useContractAnalysis';
import { AnalysisResult } from '../../features/contract/components/AnalysisResult';
import type { ContractVersion } from '../../features/contract/types';
import './contract.css';

const statusLabels: Record<string, string> = {
  pending: '等待分析',
  parsing: '解析合同文字',
  analyzing: 'AI 正在审查',
  completed: '分析完成',
  failed: '分析失败',
};

export default function ContractVersionPage() {
  const { contractId = '' } = useParams();
  const navigate = useNavigate();
  const [title, setTitle] = useState('合同详情');
  const [versions, setVersions] = useState<ContractVersion[]>([]);
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [pageError, setPageError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const { analysis, loading, error } = useContractAnalysis(contractId, selected, refreshKey);
  const running = Boolean(
    analysis && ['pending', 'parsing', 'analyzing'].includes(analysis.status),
  );

  useEffect(() => {
    let disposed = false;
    if (!selected) {
      setRuns([]);
      return;
    }
    listAnalysisRuns(contractId, selected)
      .then((response) => {
        if (!disposed) setRuns(response.data?.runs ?? []);
      })
      .catch((cause) => {
        if (!disposed) setPageError(errorText(cause));
      });
    return () => {
      disposed = true;
    };
  }, [contractId, selected, refreshKey, analysis?.latest_run_id, analysis?.status]);

  useEffect(() => {
    let disposed = false;
    setSelected('');
    setPageError('');
    Promise.all([getContract(contractId), listContractVersions(contractId)])
      .then(([contract, response]) => {
        if (disposed) return;
        const rows = response.data?.versions ?? [];
        setTitle(contract.data?.title ?? '合同详情');
        setVersions(rows);
        setSelected(rows[rows.length - 1]?.id ?? '');
      })
      .catch((cause) => {
        if (!disposed) setPageError(errorText(cause));
      });
    return () => {
      disposed = true;
    };
  }, [contractId]);

  async function upload(file: File) {
    if (file.size > 20 * 1024 * 1024 || !/\.(pdf|docx)$/i.test(file.name)) {
      message.error('请选择 20 MB 以内的 PDF / DOCX');
      return Upload.LIST_IGNORE;
    }
    setBusy(true);
    try {
      const response = await uploadContract(contractId, file);
      if (!response.success || !response.data) {
        throw new Error(response.msg || '合同上传失败');
      }
      const list = await listContractVersions(contractId);
      setVersions(list.data?.versions ?? []);
      setSelected(response.data.version_id);
      message.success('合同已上传，开始分析');
    } catch (cause) {
      message.error(errorText(cause));
    } finally {
      setBusy(false);
    }
    return false;
  }

  async function retry() {
    setBusy(true);
    try {
      await retryAnalysis(contractId, selected);
      setRefreshKey((key) => key + 1);
    } catch (cause) {
      message.error(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  async function selectRun(runId: string) {
    if (!selected || runId === analysis?.selected_run_id) return;
    setHistoryBusy(true);
    try {
      await selectAnalysisRun(contractId, selected, runId);
      setRefreshKey((key) => key + 1);
      message.success('已切换到所选历史分析');
    } catch (cause) {
      message.error(errorText(cause));
    } finally {
      setHistoryBusy(false);
    }
  }

  return (
    <main className="contract-shell">
      <header className="contract-nav">
        <Button onClick={() => navigate('/contracts')}>← 合同工作台</Button>
        <span>CONTRACT / AI REVIEW</span>
      </header>
      <section className="contract-heading">
        <div>
          <div className="eyebrow">合同审查工作区</div>
          <h1>{title}</h1>
          <p>阅读原文，查看风险依据与修改建议。</p>
        </div>
        <div className="contract-actions">
          <Select
            aria-label="合同版本"
            value={selected || undefined}
            placeholder="选择版本"
            onChange={setSelected}
            disabled={busy}
            className="version-select"
            options={versions.map((version) => ({
              value: version.id,
              label: `V${version.number} · ${version.filename}`,
            }))}
          />
          <Upload accept=".pdf,.docx" showUploadList={false} beforeUpload={upload} disabled={busy}>
            <Button type="primary" loading={busy}>
              上传{versions.length ? '新版本' : '合同'}
            </Button>
          </Upload>
        </div>
      </section>
      {(pageError || error) && (
        <Alert
          type="error"
          message={pageError || error}
          showIcon
          action={<Button onClick={() => setRefreshKey((key) => key + 1)}>刷新结果</Button>}
        />
      )}
      <div className="contract-columns">
        <section className="contract-panel">
          <div className="panel-heading">
            <h2>合同原文</h2>
            <Tag>PDF / DOCX</Tag>
          </div>
          {analysis?.document_text ? (
            <pre className="contract-document">{analysis.document_text}</pre>
          ) : (
            <div className="contract-placeholder">
              <Empty description={selected ? '解析后将在这里展示原文' : '上传合同，开始 AI 审查'} />
              {!selected && (
                <Upload
                  accept=".pdf,.docx"
                  beforeUpload={upload}
                  showUploadList={false}
                  disabled={busy}
                >
                  <Button loading={busy}>选择合同文件</Button>
                </Upload>
              )}
              <p>文字版 PDF 或 DOCX · 最大 20 MB</p>
            </div>
          )}
        </section>
        <section className="contract-panel">
          <div className="panel-heading">
            <h2>AI 分析</h2>
            <Tag color={analysis?.status === 'completed' ? 'green' : 'blue'}>
              {statusLabels[analysis?.status ?? ''] ?? '等待上传'}
            </Tag>
          </div>
          {runs.length > 0 && (
            <div className="analysis-history">
              <span>展示记录</span>
              <Select
                aria-label="分析历史"
                value={analysis?.selected_run_id ?? undefined}
                loading={historyBusy}
                disabled={historyBusy}
                placeholder="选择一次成功分析"
                onChange={(runId) => void selectRun(runId)}
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
          )}
          {analysis?.is_showing_previous && (
            <Alert
              type="info"
              showIcon
              message="当前展示的是历史成功结果"
              description="你可以在“展示记录”中切回其他成功分析，历史结果不会被覆盖。"
            />
          )}
          {(loading || running) && (
            <div className="contract-placeholder" role="status">
              <Spin />
              <h3>{statusLabels[analysis?.status ?? ''] ?? '加载中'}</h3>
              <p>正在提取关键约定和风险依据，完成后自动展示。</p>
            </div>
          )}
          {analysis?.status === 'failed' && (
            <Alert
              type="error"
              showIcon
              message="分析未完成"
              description={analysis.error}
              action={
                <Button onClick={retry} loading={busy}>
                  重新分析
                </Button>
              }
            />
          )}
          {selected && !analysis && !loading && !error && (
            <Button onClick={retry} loading={busy}>
              开始分析
            </Button>
          )}
          {analysis?.result && (
            <>
              <AnalysisResult result={analysis.result} clauses={analysis.clauses} />
              <Button onClick={retry} disabled={running} loading={busy}>
                重新分析
              </Button>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
