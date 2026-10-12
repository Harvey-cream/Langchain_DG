import { Alert, Button, Empty, Input, Select, Spin, Tag, Upload } from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import { AnalysisHistory } from './components/AnalysisHistory';
import { AnalysisResult } from './components/AnalysisResult';
import { useContractWorkspace } from './hooks/useContractWorkspace';
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
  const {
    title,
    versions,
    currentVersionId: selected,
    setCurrentVersionId: setSelected,
    analysis,
    ourParty,
    setOurParty,
    partyRole,
    setPartyRole,
    contractType,
    setContractType,
    selectedRunId,
    runs,
    loading,
    running,
    busy,
    historyBusy,
    error,
    upload,
    retry,
    selectRun,
    refresh,
  } = useContractWorkspace(contractId);

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
      <div className="review-stance">
        <label htmlFor="our-party">我方签约方</label>
        <Input
          id="our-party"
          list="contract-parties"
          value={ourParty}
          maxLength={255}
          onChange={(event) => setOurParty(event.target.value)}
          disabled={busy || running}
          placeholder="甲方、乙方或签约主体名称"
        />
        <datalist id="contract-parties">
          {analysis?.facts?.metadata.parties.map((party) => (
            <option key={party} value={party} />
          ))}
        </datalist>
        <p>下次审查使用此身份；留空按中立立场审查。</p>
        <label htmlFor="party-role">我方业务角色</label>
        <Input
          id="party-role"
          value={partyRole}
          maxLength={64}
          disabled={busy || running}
          onChange={(event) => setPartyRole(event.target.value)}
          placeholder="如 buyer / supplier（与规则范围一致）"
        />
        <label htmlFor="contract-type">合同类型</label>
        <Input
          id="contract-type"
          value={contractType}
          maxLength={64}
          disabled={busy || running}
          onChange={(event) => setContractType(event.target.value)}
          placeholder="如 procurement / technical_service"
        />
        <p>留空只使用不限制该范围的通用企业规则，不自动推断角色或合同类型。</p>
      </div>
      {error && (
        <Alert
          type="error"
          message={error}
          showIcon
          action={<Button onClick={refresh}>刷新结果</Button>}
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
          <AnalysisHistory
            runs={runs}
            selectedRunId={selectedRunId}
            busy={historyBusy}
            onSelect={(runId) => void selectRun(runId)}
          />
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
          {analysis && (analysis.result || analysis.facts) && (
            <>
              <AnalysisResult analysis={analysis} />
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
