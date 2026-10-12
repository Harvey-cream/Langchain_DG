import { Fragment, useState } from 'react';
import { Alert, Button, Drawer, Empty, Tag } from 'antd';
import type {
  Analysis,
  CanonicalClause,
  LegacyResult,
  RiskFinding,
  ReferenceSnapshot,
} from '../types';

const riskLevels = {
  high: { label: '高风险', color: 'red' },
  medium: { label: '中风险', color: 'orange' },
  low: { label: '低风险', color: 'blue' },
};

export function AnalysisResult({ analysis }: { analysis: Analysis }) {
  const [opened, setOpened] = useState<CanonicalClause>();
  const [openedReference, setOpenedReference] = useState<ReferenceSnapshot>();
  const v2 = analysis.review_version === 'v2';
  const legacy = !v2 ? (analysis.result as LegacyResult | undefined) : undefined;
  const metadata = analysis.facts?.metadata ?? legacy;
  const clauses = analysis.canonical_clauses ?? [];
  const byId = new Map(clauses.map((clause) => [clause.id, clause]));
  const policies = new Map(
    (analysis.context_snapshot?.policies ?? []).map((policy) => [policy.id, policy]),
  );
  const references = new Map(
    (analysis.context_snapshot?.references ?? []).map((reference) => [
      reference.chunk_id,
      reference,
    ]),
  );
  const quality = analysis.context_snapshot?.quality_gate;
  const events = analysis.context_snapshot?.retrieval_events ?? [];
  const risks: RiskFinding[] = v2
    ? (analysis.risks ?? []).map((risk) => ({
        clause_id: risk.clause_id ?? '',
        risk_type: risk.risk_type || risk.title,
        risk_level: risk.risk_level,
        evidence: risk.evidence ?? risk.evidence_text,
        reason: risk.reason,
        recommendation: risk.recommendation ?? risk.suggestion,
        related_clause_ids: risk.related_clause_ids ?? [],
        policy_ids: risk.policy_ids ?? [],
        reference_citations: risk.reference_citations ?? [],
      }))
    : (legacy?.risks ?? []).map((risk) => ({
        clause_id: '',
        risk_type: risk.title,
        risk_level: risk.risk_level,
        evidence: risk.original_text,
        reason: risk.reason,
        recommendation: risk.suggestion,
        related_clause_ids: [],
      }));
  const showClause = (id: string) => setOpened(byId.get(id));
  const riskCard = (risk: RiskFinding, index: number) => {
    const check = quality?.finding_checks?.find(
      (item) =>
        item.clause_id === risk.clause_id &&
        item.risk_type === risk.risk_type &&
        item.evidence === risk.evidence &&
        item.reason === risk.reason &&
        item.recommendation === risk.recommendation,
    );
    return (
      <article className={`risk-card ${risk.risk_level}`} key={`${risk.clause_id}-${index}`}>
        <Tag color={riskLevels[risk.risk_level].color}>{riskLevels[risk.risk_level].label}</Tag>
        <h3>{risk.risk_type}</h3>
        <blockquote>{risk.evidence}</blockquote>
        <p>
          {check?.assessment === 'insufficient_legal_basis' ? '待核实的模型判断：' : ''}
          {risk.reason}
        </p>
        {check?.assessment === 'insufficient_legal_basis' && (
          <Tag color="orange">法律依据未核实 · 仅供复核提示</Tag>
        )}
        {!!check?.notes.length && (
          <Alert type="warning" message="审查限制" description={check.notes.join('；')} />
        )}
        {(risk.policy_ids ?? []).length === 0 ? (
          <Tag>一般模型风险判断</Tag>
        ) : (
          (risk.policy_ids ?? []).map((id) => {
            const policy = policies.get(id);
            return (
              <div className="risk-policy" key={id}>
                <Tag color="purple">
                  企业规则：{policy?.name ?? id} · v{policy?.version}
                </Tag>
                <p>{policy?.requirement}</p>
              </div>
            );
          })
        )}
        <div className="risk-suggestion">
          <strong>审查建议（待确认）</strong>
          <p>{risk.recommendation}</p>
        </div>
        {v2 && (
          <>
            {(risk.reference_citations ?? []).map((citation) => {
              const reference = references.get(citation.chunk_id);
              return (
                <div className="risk-reference" key={citation.chunk_id}>
                  <Tag color="cyan">RAG 参考资料（非强制政策）</Tag>
                  <p>
                    {reference?.filename ?? '历史参考资料'} · 文档 v{reference?.document_version} ·
                    索引代次 {reference?.index_generation}
                  </p>
                  <blockquote>{citation.source_excerpt}</blockquote>
                  {!!reference?.locator.pages?.length && (
                    <p>来源页码：{reference.locator.pages.join('、')}</p>
                  )}
                  <Button type="link" onClick={() => setOpenedReference(reference)}>
                    查看参考快照
                  </Button>
                </div>
              );
            })}
            <Button type="link" onClick={() => showClause(risk.clause_id)}>
              查看关联条款
            </Button>
          </>
        )}
        {risk.related_clause_ids.map((id) => (
          <Button type="link" key={id} onClick={() => showClause(id)}>
            相关条款：{byId.get(id)?.title ?? id}
          </Button>
        ))}
      </article>
    );
  };
  return (
    <>
      {metadata && (
        <div className="analysis-summary">
          <h3>合同概览</h3>
          <p>{metadata.summary}</p>
          <dl>
            {[
              ['签约双方', metadata.parties.join(' / ')],
              ['合同金额', metadata.amount],
              ['合同期限', metadata.duration],
              ['付款条件', metadata.payment_terms],
            ].map(([label, value]) => (
              <Fragment key={label}>
                <dt>{label}</dt>
                <dd>{value || '未提取到明确约定'}</dd>
              </Fragment>
            ))}
          </dl>
        </div>
      )}
      {analysis.facts && analysis.facts.coverage.ratio < 1 && (
        <Alert
          type="warning"
          showIcon
          message={`条款覆盖率 ${Math.round(analysis.facts.coverage.ratio * 100)}%，请结合合同原文复核。`}
        />
      )}
      {analysis.result && (
        <>
          <Tag>{v2 ? 'Review V2' : '历史 Review V1'}</Tag>
          {v2 && quality?.status === 'passed' && (
            <Alert
              type="info"
              showIcon
              message="当前展示结果已通过来源校验，不代表法律结论正确"
              description={`合同原文、规则与引用来源已校验，建议仍需业务或法务确认。${quality.duplicate_count ? `已移除 ${quality.duplicate_count} 条确定重复风险，原始记录仍保留。` : ''}`}
            />
          )}
          {v2 && !quality && <p>历史结果未记录本版质量校验，不能追认为已通过。</p>}
          {!!quality?.warnings?.length && (
            <Alert type="warning" message={quality.warnings.join('；')} />
          )}
          {events.some((event) => event.unavailable_count) && (
            <p>部分参考资料在检索期间撤下，已排除；未补写缺失引用。</p>
          )}
          {!!references.size && events.some((event) => !event.reference_count) && (
            <p>部分条款没有可用参考资料，请结合合同原文复核。</p>
          )}
          <p>本次审查立场：{analysis.our_party || '未指定我方身份，中立审查'}</p>
          {!!analysis.context_snapshot?.retrieval?.enabled && !references.size && (
            <p>本次没有提供知识库参考资料，风险不代表已获得企业案例或法规检索支持。</p>
          )}
          <div className="risk-counts">
            {(Object.keys(riskLevels) as Array<keyof typeof riskLevels>).map((level) => (
              <span key={level}>
                {riskLevels[level].label}
                <b>{risks.filter((risk) => risk.risk_level === level).length}</b>
              </span>
            ))}
          </div>
        </>
      )}
      {analysis.latest_quality_gate?.status === 'failed' && (
        <Alert type="error" showIcon message="最新审查未通过质量校验，未保存为成功结果" />
      )}
      {clauses.length > 0 && (
        <div className="clause-list">
          <h3>版本条款</h3>
          {clauses.map((clause) => (
            <section key={clause.id} data-clause-id={clause.id}>
              <article className="clause-card">
                <span>#{clause.sequence}</span>
                <div>
                  <strong>{clause.title}</strong>
                  <Tag>{clause.clause_type}</Tag>
                  <details>
                    <summary>查看条款原文</summary>
                    <pre className="clause-source">{clause.original_text}</pre>
                  </details>
                </div>
              </article>
              {v2 && risks.filter((risk) => risk.clause_id === clause.id).map(riskCard)}
            </section>
          ))}
        </div>
      )}
      {!v2 && (
        <>
          {!!analysis.clauses?.length && (
            <div className="clause-list">
              <h3>历史审查条款</h3>
              {analysis.clauses.map((clause) => (
                <article key={clause.id} className="clause-card">
                  <span>#{clause.sequence}</span>
                  <div>
                    <strong>{clause.title}</strong>
                    <p>{clause.summary || clause.original_text}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
          {risks.map(riskCard)}
        </>
      )}
      {analysis.result && !risks.length && <Empty description="本次分析未识别到风险项" />}
      <Drawer
        title={opened ? `条款 #${opened.sequence} ${opened.title}` : ''}
        open={Boolean(opened)}
        onClose={() => setOpened(undefined)}
        width="min(600px, 100vw)"
      >
        <pre className="clause-source">{opened?.original_text}</pre>
        {!!opened?.pages.length && <p>来源页码：{opened.pages.join('、')}</p>}
      </Drawer>
      <Drawer
        title={openedReference?.filename}
        open={Boolean(openedReference)}
        onClose={() => setOpenedReference(undefined)}
        width="min(600px, 100vw)"
      >
        <p>审查时保存的引用快照；原件删除或重建索引不会覆盖此依据。</p>
        <pre className="clause-source">{openedReference?.chunk_text}</pre>
        {!!openedReference?.locator.block_sequences?.length && (
          <p>来源块：{openedReference.locator.block_sequences.join('、')}</p>
        )}
      </Drawer>
      <p className="analysis-note">通用商业风险分析，建议尚待业务或法务人员确认。</p>
    </>
  );
}
