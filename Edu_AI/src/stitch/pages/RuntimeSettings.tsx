import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Skeleton,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import {
  ApiOutlined,
  AudioOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import {
  activateRuntimeConfig,
  getRuntimeConfigOverview,
  rollbackRuntimeConfig,
  saveRuntimeConfigDraft,
  verifyRuntimeConfig,
  type RuntimeConfigOverview,
  type RuntimeConfigScope,
  type RuntimeProvider,
  type RuntimeProviderStatus,
} from "../api/runtimeConfig";
import { AppSurface, MaterialIcon, routeHref, routes } from "../shared";

const { Paragraph, Text, Title } = Typography;

const providerMeta: Record<
  RuntimeProvider,
  { title: string; description: string; icon: React.ReactNode }
> = {
  llm: {
    title: "对话与内容模型",
    description: "用于问答、报告、教案、习题和生成工厂。",
    icon: <ApiOutlined />,
  },
  embedding: {
    title: "知识库向量模型",
    description: "用于资料入库、检索和相似内容匹配。",
    icon: <DatabaseOutlined />,
  },
  tts: {
    title: "语音合成",
    description: "为 AI 课堂讲解生成并保存配音。",
    icon: <AudioOutlined />,
  },
  web_search: {
    title: "联网搜索",
    description: "用于深度搜索和课程资料补充。",
    icon: <GlobalOutlined />,
  },
  pdf_parser: {
    title: "PDF 解析",
    description: "用于提取教材、论文和讲义的结构化内容。",
    icon: <FileSearchOutlined />,
  },
  classroom: {
    title: "AI 课堂服务",
    description: "连接课堂生成与交互课件服务。",
    icon: <CloudServerOutlined />,
  },
};

const fieldMeta: Record<string, { label: string; placeholder: string; secret?: boolean }> = {
  base_url: { label: "服务地址", placeholder: "https://api.example.com/v1" },
  api_key: { label: "API 密钥", placeholder: "仅本次填写，不会再次明文显示", secret: true },
  model: { label: "模型名称", placeholder: "例如 gpt-5-mini" },
  voice: { label: "默认音色", placeholder: "例如 alloy" },
  dimensions: { label: "向量维度", placeholder: "留空则使用服务默认值" },
};

const statusMeta = {
  active: { color: "success", label: "已启用" },
  verified: { color: "processing", label: "测试通过" },
  invalid: { color: "error", label: "测试失败" },
  draft: { color: "default", label: "待测试" },
  superseded: { color: "warning", label: "历史版本" },
} as const;

function sourceLabel(source: RuntimeProviderStatus["effective_source"]) {
  if (source === "user") return "个人配置生效";
  if (source === "system") return "系统配置生效";
  return "使用部署默认值";
}

export function RuntimeSettingsPage() {
  const [overview, setOverview] = useState<RuntimeConfigOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");
  const [scope, setScope] = useState<RuntimeConfigScope>("user");
  const [editing, setEditing] = useState<RuntimeProviderStatus | null>(null);
  const [form] = Form.useForm<Record<string, string | number>>();

  async function load() {
    setLoading(true);
    try {
      setOverview(await getRuntimeConfigOverview());
    } catch (error) {
      message.error(error instanceof Error ? error.message : "配置状态加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const visibleProviders = useMemo(() => overview?.providers ?? [], [overview]);

  function recordFor(item: RuntimeProviderStatus) {
    return scope === "system" ? item.system : item.user;
  }

  function openEditor(item: RuntimeProviderStatus) {
    setEditing(item);
    const latest = recordFor(item)?.revisions[0];
    const safeValues = Object.fromEntries(
      Object.entries(latest?.values ?? {}).filter(([field]) => field !== "api_key"),
    );
    form.setFieldsValue(safeValues);
  }

  async function saveDraft() {
    if (!editing) return;
    const values = await form.validateFields();
    setBusyKey(`${editing.provider}:save`);
    try {
      await saveRuntimeConfigDraft(editing.provider, scope, values);
      message.success("草稿已安全保存，请测试连接后再启用");
      setEditing(null);
      form.resetFields();
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setBusyKey("");
    }
  }

  async function runAction(
    item: RuntimeProviderStatus,
    action: "verify" | "activate" | "rollback",
    revisionId?: string,
  ) {
    const key = `${item.provider}:${action}`;
    setBusyKey(key);
    try {
      if (action === "verify" && revisionId) {
        const result = await verifyRuntimeConfig(item.provider, scope, revisionId);
        result.status === "verified"
          ? message.success("连接测试通过，现在可以启用")
          : message.error(result.validation_error || "连接测试失败");
      } else if (action === "activate" && revisionId) {
        await activateRuntimeConfig(item.provider, scope, revisionId);
        message.success("配置已启用，新任务将使用该版本");
      } else {
        await rollbackRuntimeConfig(item.provider, scope);
        message.success("已回滚到上一条可用配置");
      }
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "操作失败");
    } finally {
      setBusyKey("");
    }
  }

  return (
    <AppSurface className="min-h-screen bg-[linear-gradient(180deg,#f4f8ff_0%,#e9effa_100%)]">
      <main className="mx-auto w-full max-w-[1500px] px-5 py-7 sm:px-8 lg:px-10">
        <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <a
              href={routeHref(routes.profile)}
              className="grid h-11 w-11 place-items-center rounded-full border border-[#cbd8ed] bg-white text-[#17304a] shadow-sm"
              aria-label="返回账号中心"
            >
              <MaterialIcon name="arrow_back" />
            </a>
            <div>
              <Text className="text-xs font-bold uppercase tracking-[0.2em] text-[#56709a]">
                Service Configuration
              </Text>
              <Title level={2} className="!mb-0 !mt-1 !text-[#132f52]">
                AI 服务配置
              </Title>
            </div>
          </div>
          {overview?.can_manage_system ? (
            <Segmented
              value={scope}
              onChange={(value) => setScope(value as RuntimeConfigScope)}
              options={[
                { label: "个人配置", value: "user" },
                { label: "系统配置", value: "system" },
              ]}
            />
          ) : (
            <Tag color="blue">个人配置</Tag>
          )}
        </div>

        <Alert
          className="mb-7 rounded-2xl border-[#c9dbff] bg-[#eef5ff]"
          icon={<SafetyCertificateOutlined />}
          showIcon
          message="密钥由后端加密保存，页面不会回显明文"
          description="保存只会创建草稿；连接测试成功后才能启用。正在运行的任务继续使用启动时的配置版本。"
        />

        {loading && !overview ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <Card key={index} className="rounded-[24px]"><Skeleton active /></Card>
            ))}
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {visibleProviders.map((item) => {
              const record = recordFor(item);
              const latest = record?.revisions[0];
              const active = record?.revisions.find(
                (revision) => revision.revision_id === record.active_revision_id,
              );
              const status = latest ? statusMeta[latest.status] : null;
              const canRollback = Boolean(
                active && record?.revisions.some((revision) => revision.status === "superseded"),
              );
              return (
                <Card
                  key={item.provider}
                  className="overflow-hidden rounded-[26px] border-[#d7e1f0] shadow-[0_16px_34px_rgba(37,71,117,0.08)]"
                  styles={{ body: { padding: 24 } }}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="grid h-12 w-12 place-items-center rounded-2xl bg-[#e8f0ff] text-xl text-[#2357b8]">
                      {providerMeta[item.provider].icon}
                    </div>
                    {status ? <Tag color={status.color}>{status.label}</Tag> : <Tag>未配置</Tag>}
                  </div>
                  <Title level={4} className="!mb-1 !mt-5 !text-[#17304a]">
                    {providerMeta[item.provider].title}
                  </Title>
                  <Paragraph className="!mb-4 min-h-11 !text-[#60738f]">
                    {providerMeta[item.provider].description}
                  </Paragraph>
                  <div className="mb-5 rounded-2xl bg-[#f5f8fd] px-4 py-3">
                    <Text className="text-xs font-semibold text-[#60738f]">当前来源</Text>
                    <div className="mt-1 font-bold text-[#17304a]">
                      {scope === "system"
                        ? active ? "系统配置生效" : "使用部署默认值"
                        : sourceLabel(item.effective_source)}
                    </div>
                    {active?.values.model ? (
                      <Text className="mt-1 block text-xs text-[#60738f]">
                        模型：{String(active.values.model)}
                      </Text>
                    ) : null}
                  </div>
                  {latest?.validation_error ? (
                    <Alert
                      className="mb-4"
                      type="error"
                      showIcon
                      message={latest.validation_error}
                    />
                  ) : null}
                  <Space wrap>
                    <Button type="primary" onClick={() => openEditor(item)}>
                      {latest ? "新建配置" : "开始配置"}
                    </Button>
                    {latest && ["draft", "invalid"].includes(latest.status) ? (
                      <Button
                        loading={busyKey === `${item.provider}:verify`}
                        onClick={() => void runAction(item, "verify", latest.revision_id)}
                      >
                        测试连接
                      </Button>
                    ) : null}
                    {latest?.status === "verified" ? (
                      <Button
                        loading={busyKey === `${item.provider}:activate`}
                        onClick={() => void runAction(item, "activate", latest.revision_id)}
                      >
                        启用
                      </Button>
                    ) : null}
                    {canRollback ? (
                      <Button
                        icon={<ReloadOutlined />}
                        loading={busyKey === `${item.provider}:rollback`}
                        onClick={() => void runAction(item, "rollback")}
                      >
                        回滚
                      </Button>
                    ) : null}
                  </Space>
                </Card>
              );
            })}
          </div>
        )}
      </main>

      <Modal
        title={editing ? `配置${providerMeta[editing.provider].title}` : "配置服务"}
        open={Boolean(editing)}
        okText="保存草稿"
        cancelText="取消"
        confirmLoading={Boolean(editing && busyKey === `${editing.provider}:save`)}
        onOk={() => void saveDraft()}
        onCancel={() => {
          setEditing(null);
          form.resetFields();
        }}
        destroyOnHidden
      >
        <Alert
          className="mb-5"
          type="info"
          showIcon
          message="API 密钥每次新建配置都需重新填写，旧密钥不会回显。"
        />
        <Form form={form} layout="vertical" requiredMark={false}>
          {editing?.fields.map((field) => {
            const meta = fieldMeta[field] ?? { label: field, placeholder: "" };
            return (
              <Form.Item
                key={field}
                name={field}
                label={meta.label}
                rules={[
                  ...(field === "base_url" || field === "api_key"
                    ? [{ required: true, message: `请填写${meta.label}` }]
                    : []),
                  ...(field === "model" && ["llm", "embedding", "tts"].includes(editing.provider)
                    ? [{ required: true, message: "请填写模型名称" }]
                    : []),
                ]}
              >
                {field === "dimensions" ? (
                  <InputNumber className="w-full" min={1} placeholder={meta.placeholder} />
                ) : meta.secret ? (
                  <Input.Password
                    autoComplete="new-password"
                    visibilityToggle={false}
                    placeholder={meta.placeholder}
                  />
                ) : (
                  <Input placeholder={meta.placeholder} />
                )}
              </Form.Item>
            );
          })}
        </Form>
      </Modal>
    </AppSurface>
  );
}
