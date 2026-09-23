import { Fragment } from 'react';
import { Empty, Tag } from 'antd';
import type { Analysis } from '../api/demo';

const riskLevels = {
  high: { label: '高风险', color: 'red' },
  medium: { label: '中风险', color: 'orange' },
  low: { label: '低风险', color: 'blue' },
};

export function AnalysisResult({
  result,
  clauses = [],
}: {
  result: NonNullable<Analysis['result']>;
  clauses?: NonNullable<Analysis['clauses']>;
}) {
  const details = [
    ['签约双方', result.parties.join(' / ')],
    ['合同金额', result.amount],
    ['合同期限', result.duration],
    ['付款条件', result.payment_terms],
  ];

  return (
    <>
      <div className="analysis-summary">
        <Tag>{result.document_type}</Tag>
        <h3>合同概览</h3>
        <p>{result.summary}</p>
        <dl>
          {details.map(([label, value]) => (
            <Fragment key={label}>
              <dt>{label}</dt>
              <dd>{value || '未约定'}</dd>
            </Fragment>
          ))}
        </dl>
        {result.key_obligations.length > 0 && (
          <>
            <h3>主要义务</h3>
            <ul>
              {result.key_obligations.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </>
        )}
      </div>
      {clauses.length > 0 && (
        <div className="clause-list">
          <h3>关键条款</h3>
          {clauses.map((clause) => (
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
      <div className="risk-counts">
        {(Object.keys(riskLevels) as Array<keyof typeof riskLevels>).map((level) => (
          <span key={level}>
            {riskLevels[level].label}
            <b>{result.risks.filter((risk) => risk.risk_level === level).length}</b>
          </span>
        ))}
      </div>
      {result.risks.map((risk, index) => (
        <article className={`risk-card ${risk.risk_level}`} key={index}>
          <Tag color={riskLevels[risk.risk_level].color}>{riskLevels[risk.risk_level].label}</Tag>
          <h3>{risk.title}</h3>
          <blockquote>{risk.original_text}</blockquote>
          <p>{risk.reason}</p>
          <div className="risk-suggestion">
            <strong>修改建议</strong>
            <p>{risk.suggestion}</p>
          </div>
        </article>
      ))}
      {!result.risks.length && <Empty description="本次分析未识别到风险项" />}
      <p className="analysis-note">
        通用商业风险分析，未应用企业专属政策。建议由业务或法务人员确认。
      </p>
    </>
  );
}
