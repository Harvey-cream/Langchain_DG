import { useEffect, useMemo, useState } from 'react';
import { Upload, message } from 'antd';
import { listContractVersions } from '../api';
import {
  errorText,
  getContract,
  listAnalysisRuns,
  retryAnalysis,
  selectAnalysisRun,
  uploadContract,
} from '../api/demo';
import type { AnalysisRun } from '../api/demo';
import type { ContractVersion } from '../types';
import { useContractAnalysis } from './useContractAnalysis';

const ACTIVE_STATUSES = ['pending', 'parsing', 'analyzing'];

export function useContractWorkspace(contractId: string) {
  const [title, setTitle] = useState('合同详情');
  const [versions, setVersions] = useState<ContractVersion[]>([]);
  const [currentVersionId, setCurrentVersionId] = useState('');
  const [busy, setBusy] = useState(false);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [pageError, setPageError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);
  const {
    analysis,
    loading,
    error: analysisError,
  } = useContractAnalysis(contractId, currentVersionId, refreshKey);

  const currentVersion = useMemo(
    () => versions.find((version) => version.id === currentVersionId),
    [versions, currentVersionId],
  );
  const running = Boolean(analysis && ACTIVE_STATUSES.includes(analysis.status));

  useEffect(() => {
    let disposed = false;
    if (!currentVersionId) {
      setRuns([]);
      return;
    }
    listAnalysisRuns(contractId, currentVersionId)
      .then((response) => {
        if (!disposed) setRuns(response.data?.runs ?? []);
      })
      .catch((cause) => {
        if (!disposed) setPageError(errorText(cause));
      });
    return () => {
      disposed = true;
    };
  }, [contractId, currentVersionId, refreshKey, analysis?.latest_run_id, analysis?.status]);

  useEffect(() => {
    let disposed = false;
    setCurrentVersionId('');
    setPageError('');
    Promise.all([getContract(contractId), listContractVersions(contractId)])
      .then(([contract, response]) => {
        if (disposed) return;
        const rows = response.data?.versions ?? [];
        setTitle(contract.data?.title ?? '合同详情');
        setVersions(rows);
        setCurrentVersionId(rows[rows.length - 1]?.id ?? '');
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
      setCurrentVersionId(response.data.version_id);
      message.success('合同已上传，开始分析');
    } catch (cause) {
      message.error(errorText(cause));
    } finally {
      setBusy(false);
    }
    return false;
  }

  async function retry() {
    if (!currentVersionId) return;
    setBusy(true);
    try {
      await retryAnalysis(contractId, currentVersionId);
      setRefreshKey((key) => key + 1);
    } catch (cause) {
      message.error(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  async function selectRun(runId: string) {
    if (!currentVersionId || runId === analysis?.selected_run_id) return;
    setHistoryBusy(true);
    try {
      await selectAnalysisRun(contractId, currentVersionId, runId);
      setRefreshKey((key) => key + 1);
      message.success('已切换到所选历史分析');
    } catch (cause) {
      message.error(errorText(cause));
    } finally {
      setHistoryBusy(false);
    }
  }

  return {
    title,
    versions,
    currentVersion,
    currentVersionId,
    setCurrentVersionId,
    analysis,
    selectedRunId: analysis?.selected_run_id ?? undefined,
    runs,
    loading,
    running,
    busy,
    historyBusy,
    error: pageError || analysisError,
    upload,
    retry,
    selectRun,
    refresh: () => setRefreshKey((key) => key + 1),
  };
}
