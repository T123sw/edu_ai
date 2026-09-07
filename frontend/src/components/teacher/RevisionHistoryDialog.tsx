import { useState } from 'react';
import { Alert, Button, InputNumber, Modal, Spin } from 'antd';
import type { ArtifactRevisionReference } from '../../stitch/artifactRevision/intent';
import type { CourseMaterial } from '../../stitch/api/types';
import { CourseMaterialArtifactPreview } from '../../stitch/pages/CourseMaterialArtifactPreview';
import { readArtifactRevision, restoreArtifactRevision, type ArtifactRevisionOutcome } from '../../services/teacher/chatV2';

export function RevisionHistoryDialog({ reference, onClose, onRestored }: {
  reference: ArtifactRevisionReference;
  onClose: () => void;
  onRestored: (outcome: ArtifactRevisionOutcome) => void;
}) {
  const currentVersion = Number(reference.version_id.replace(/^v/, ''));
  const [version, setVersion] = useState(Math.max(1, currentVersion - 1));
  const [preview, setPreview] = useState<CourseMaterial | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const restore = async () => {
    setSaving(true);
    setError('');
    try {
      const result = await restoreArtifactRevision(reference, version, crypto.randomUUID());
      if (result.status !== 'completed') { setError(result.message); return; }
      onRestored(result);
      onClose();
    } catch (error) {
      setError(error instanceof Error ? error.message : '恢复失败');
    } finally { setSaving(false); }
  };
  return <Modal open title="查看历史版本与恢复" width={900} onCancel={onClose} onOk={() => void restore()}
    okText="恢复为新版本" cancelText="关闭" confirmLoading={saving} okButtonProps={{ disabled: !preview || loading }}>
    <p>恢复会保存一个新版本，并保留现有历史。</p>
    <div className="flex flex-wrap items-center gap-2">
      <span>历史版本</span>
      <InputNumber disabled={loading || saving} aria-label="历史版本" min={1} max={Math.max(1, currentVersion - 1)} value={version} onChange={value => { setVersion(value || 1); setPreview(null); }} />
      <Button disabled={saving} loading={loading} onClick={async () => {
        setLoading(true); setError(''); setPreview(null);
        try { setPreview(await readArtifactRevision(reference, version)); }
        catch (error) { setError(error instanceof Error ? error.message : '版本读取失败'); }
        finally { setLoading(false); }
      }}>查看此版本</Button>
    </div>
    {error && <Alert type="error" message={error} className="mt-3" />}
    <Spin spinning={loading}><div className="mt-3 max-h-[55vh] overflow-auto">{preview && <CourseMaterialArtifactPreview material={preview} />}</div></Spin>
  </Modal>;
}
