import { useEffect, useMemo, useState, type ReactNode } from "react";
import Alert from "antd/es/alert";
import Button from "antd/es/button";
import Form from "antd/es/form";
import Input from "antd/es/input";
import InputNumber from "antd/es/input-number";
import Segmented from "antd/es/segmented";
import Skeleton from "antd/es/skeleton";
import Tag from "antd/es/tag";
import Typography from "antd/es/typography";
import message from "antd/es/message";
import ApiOutlined from "@ant-design/icons/es/icons/ApiOutlined.js";
import AudioOutlined from "@ant-design/icons/es/icons/AudioOutlined.js";
import CheckCircleFilled from "@ant-design/icons/es/icons/CheckCircleFilled.js";
import CloudServerOutlined from "@ant-design/icons/es/icons/CloudServerOutlined.js";
import DatabaseOutlined from "@ant-design/icons/es/icons/DatabaseOutlined.js";
import FileSearchOutlined from "@ant-design/icons/es/icons/FileSearchOutlined.js";
import GlobalOutlined from "@ant-design/icons/es/icons/GlobalOutlined.js";
import SafetyCertificateOutlined from "@ant-design/icons/es/icons/SafetyCertificateOutlined.js";
import {
  activateRuntimeConfig,
  disableRuntimeConfig,
  getRuntimeConfigOverview,
  saveRuntimeConfigDraft,
  verifyRuntimeConfig,
  type RuntimeConfigOverview,
  type RuntimeConfigScope,
  type RuntimeProvider,
  type RuntimeProviderStatus,
} from "../api/runtimeConfig";
import { AppSurface, MaterialIcon, routeHref, routes } from "../shared";

const { Text, Title } = Typography;

type ProviderMeta = {
  title: string;
  shortTitle: string;
  description: string;
  usage: string;
  icon: ReactNode;
};

const providerMeta: Record<RuntimeProvider, ProviderMeta> = {
  llm: {
    title: "对话与内容模型",
    shortTitle: "对话生成",
    description: "统一配置教师问答、报告、教案、习题和生成工厂使用的内容模型。",
    usage: "问答 · 报告 · 教案 · 习题",
    icon: <ApiOutlined />,
  },
  embedding: {
    title: "知识库向量模型",
    shortTitle: "向量检索",
    description: "负责课程资料入库、RAG 检索以及相似内容匹配。",
    usage: "资料入库 · RAG 检索",
    icon: <DatabaseOutlined />,
  },
  tts: {
    title: "语音服务",
    shortTitle: "语音服务",
    description: "为 AI 课堂讲解生成并保存配音，可设置模型和默认音色。",
    usage: "课堂讲解 · 音频生成",
    icon: <AudioOutlined />,
  },
  web_search: {
    title: "联网搜索服务",
    shortTitle: "联网搜索",
    description: "用于深度搜索、图片检索和课程资料补充。",
    usage: "深度搜索 · 资料补充",
    icon: <GlobalOutlined />,
  },
  pdf_parser: {
    title: "文档解析服务",
    shortTitle: "文档解析",
    description: "提取教材、论文和讲义的结构化内容，供知识库继续处理。",
    usage: "PDF · 教材 · 论文",
    icon: <FileSearchOutlined />,
  },
  classroom: {
    title: "AI 课堂服务",
    shortTitle: "AI 课堂",
    description: "连接课堂生成与交互课件服务，支持课堂内容生产。",
    usage: "课堂生成 · 交互课件",
    icon: <CloudServerOutlined />,
  },
};

const fieldMeta: Record<
  string,
  { label: string; placeholder: string; hint?: string; secret?: boolean }
> = {
  provider_name: {
    label: "服务商名称",
    placeholder: "例如 OpenAI、Ollama、Bocha",
    hint: "仅用于识别当前配置，不影响请求协议。",
  },
  base_url: {
    label: "服务地址",
    placeholder: "https://api.example.com/v1",
    hint: "请填写完整的 HTTP 或 HTTPS 地址。",
  },
  api_key: {
    label: "API 密钥",
    placeholder: "请输入新的 API 密钥",
    hint: "密钥只提交给后端加密保存，保存后不再显示明文。",
    secret: true,
  },
  model: {
    label: "模型或服务标识",
    placeholder: "例如 qwen-plus、text-embedding-3-small",
  },
  voice: {
    label: "默认音色",
    placeholder: "例如 alloy",
  },
  dimensions: {
    label: "向量维度",
    placeholder: "留空则使用服务默认值",
  },
  timeout_seconds: {
    label: "请求超时",
    placeholder: "1～120 秒",
    hint: "网络较慢或生成任务较长时可适当调高。",
  },
};

const statusMeta = {
  active: { color: "success", label: "已应用" },
  disabled: { color: "default", label: "已停用" },
  verified: { color: "processing", label: "测试通过" },
  invalid: { color: "error", label: "测试失败" },
  draft: { color: "default", label: "待测试" },
  superseded: { color: "warning", label: "历史版本" },
} as const;

type FormValues = Record<string, string | number>;
type TestedRevision = {
  provider: RuntimeProvider;
  scope: RuntimeConfigScope;
  revisionId: string;
};

function sourceLabel(
  source: RuntimeProviderStatus["effective_source"],
  scope: RuntimeConfigScope,
  hasActive: boolean,
) {
  if (scope === "system") return hasActive ? "系统配置正在生效" : "使用部署环境配置";
  if (source === "user") return "个人配置正在生效";
  if (source === "system") return "继承系统配置";
  return "使用部署环境配置";
}

function activeRevision(
  item: RuntimeProviderStatus,
  scope: RuntimeConfigScope,
) {
  const record = scope === "system" ? item.system : item.user;
  return record?.revisions.find(
    (revision) => revision.revision_id === record.active_revision_id,
  );
}

export function RuntimeSettingsPage() {
  const [overview, setOverview] = useState<RuntimeConfigOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");
  const [scope, setScope] = useState<RuntimeConfigScope>("user");
  const [selectedProvider, setSelectedProvider] =
    useState<RuntimeProvider>("llm");
  const [testedRevision, setTestedRevision] =
    useState<TestedRevision | null>(null);
  const [form] = Form.useForm<FormValues>();

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
  const selectedItem = useMemo(
    () =>
      visibleProviders.find((item) => item.provider === selectedProvider) ??
      visibleProviders[0] ??
      null,
    [selectedProvider, visibleProviders],
  );
  const selectedRecord = selectedItem
    ? scope === "system"
      ? selectedItem.system
      : selectedItem.user
    : null;
  const latest = selectedRecord?.revisions[0];
  const active = selectedItem ? activeRevision(selectedItem, scope) : undefined;
  const testedForCurrent =
    testedRevision?.provider === selectedItem?.provider &&
    testedRevision?.scope === scope
      ? testedRevision
      : null;

  useEffect(() => {
    if (!selectedItem) return;
    const record = scope === "system" ? selectedItem.system : selectedItem.user;
    const testedRevisionId =
      testedRevision?.provider === selectedItem.provider &&
      testedRevision.scope === scope
        ? testedRevision.revisionId
        : null;
    const revision =
      record?.revisions.find(
        (candidate) => candidate.revision_id === testedRevisionId,
      ) ??
      record?.revisions.find(
        (candidate) => candidate.revision_id === record.active_revision_id,
      ) ??
      record?.revisions[0];
    const safeValues = Object.fromEntries(
      Object.entries(revision?.values ?? {}).filter(([field]) => field !== "api_key"),
    );
    form.resetFields();
    form.setFieldsValue(safeValues);
  }, [form, overview, scope, selectedItem, testedRevision]);

  function selectProvider(provider: RuntimeProvider) {
    setSelectedProvider(provider);
    setTestedRevision(null);
  }

  function changeScope(value: string | number) {
    setScope(value as RuntimeConfigScope);
    setTestedRevision(null);
  }

  async function testConnection() {
    if (!selectedItem) return;
    const values = await form.validateFields();
    const key = `${selectedItem.provider}:test`;
    setBusyKey(key);
    setTestedRevision(null);
    try {
      const draft = await saveRuntimeConfigDraft(
        selectedItem.provider,
        scope,
        values,
      );
      const verified = await verifyRuntimeConfig(
        selectedItem.provider,
        scope,
        draft.revision_id,
      );
      if (verified.status !== "verified") {
        message.error(verified.validation_error || "连接测试失败，请检查配置");
        await load();
        return;
      }
      setTestedRevision({
        provider: selectedItem.provider,
        scope,
        revisionId: verified.revision_id,
      });
      message.success("测试通过，可以应用配置");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "连接测试失败");
    } finally {
      setBusyKey("");
    }
  }

  async function applyConfiguration() {
    if (!selectedItem || !testedForCurrent) {
      message.warning("请先测试当前配置");
      return;
    }
    const key = `${selectedItem.provider}:apply`;
    setBusyKey(key);
    try {
      await activateRuntimeConfig(
        selectedItem.provider,
        scope,
        testedForCurrent.revisionId,
      );
      setTestedRevision(null);
      message.success("配置已应用，新任务将使用该版本");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "应用配置失败");
    } finally {
      setBusyKey("");
    }
  }

  async function restoreDefault() {
    if (!selectedItem || !active) return;
    const key = `${selectedItem.provider}:disable`;
    setBusyKey(key);
    try {
      await disableRuntimeConfig(selectedItem.provider, scope);
      setTestedRevision(null);
      message.success("已恢复使用下一层默认配置");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "恢复默认配置失败");
    } finally {
      setBusyKey("");
    }
  }

  return (
    <AppSurface className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(219,234,254,0.68),transparent_27%),linear-gradient(180deg,#f5f8fd_0%,#eaf0f9_100%)]">
      <main className="mx-auto w-full max-w-[1480px] px-5 py-7 sm:px-8 lg:px-10">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <a
              href={routeHref(routes.profile)}
              className="grid h-11 w-11 place-items-center rounded-full border border-[#cbd8ed] bg-white text-[#17304a] shadow-sm transition hover:border-[#93b4ed] hover:text-[#1d4ed8]"
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
              <Text className="mt-1 block text-sm text-[#60738f]">
                按服务选择配置，测试通过后再应用。
              </Text>
            </div>
          </div>
          {overview?.can_manage_system ? (
            <Segmented
              value={scope}
              onChange={changeScope}
              options={[
                { label: "个人配置", value: "user" },
                { label: "系统配置", value: "system" },
              ]}
            />
          ) : (
            <Tag color="blue">个人配置</Tag>
          )}
        </header>

        <div className="grid min-h-[680px] overflow-hidden rounded-[28px] border border-[#d7e1f0] bg-white shadow-[0_24px_64px_rgba(37,71,117,0.12)] lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="runtime-service-nav border-b border-[#dce5f2] bg-[#f7f9fd] p-4 lg:border-b-0 lg:border-r">
            <div className="mb-4 px-3 pt-2">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#7184a1]">
                服务目录
              </p>
              <p className="mt-2 text-sm leading-6 text-[#60738f]">
                这些服务对应系统运行时实际使用的 API。
              </p>
            </div>

            {loading && !overview ? (
              <div className="space-y-3 px-2">
                {Array.from({ length: 6 }).map((_, index) => (
                  <Skeleton.Button
                    key={index}
                    active
                    block
                    className="!h-[68px]"
                  />
                ))}
              </div>
            ) : (
              <nav className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1" aria-label="AI 服务目录">
                {visibleProviders.map((item) => {
                  const meta = providerMeta[item.provider];
                  const isSelected = item.provider === selectedItem?.provider;
                  const itemActive = activeRevision(item, scope);
                  const record = scope === "system" ? item.system : item.user;
                  const status = record?.revisions[0]?.status;
                  return (
                    <button
                      key={item.provider}
                      type="button"
                      onClick={() => selectProvider(item.provider)}
                      className={`group flex min-w-0 items-center gap-3 rounded-[18px] border px-3 py-3 text-left transition ${
                        isSelected
                          ? "border-[#b7cff8] bg-white text-[#174ea6] shadow-[0_10px_24px_rgba(37,99,235,0.11)]"
                          : "border-transparent text-[#40536d] hover:border-[#d8e4f6] hover:bg-white"
                      }`}
                      aria-current={isSelected ? "page" : undefined}
                    >
                      <span
                        className={`grid h-11 w-11 flex-none place-items-center rounded-[14px] ${
                          isSelected
                            ? "bg-[#e8f1ff] text-[#2563eb]"
                            : "bg-white text-[#6b7f9c]"
                        }`}
                      >
                        {meta.icon}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-bold">
                          {meta.shortTitle}
                        </span>
                        <span className="mt-1 flex items-center gap-1.5 text-xs text-[#7b8da7]">
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              itemActive ? "bg-emerald-500" : "bg-slate-300"
                            }`}
                          />
                          {status ? statusMeta[status].label : "使用默认配置"}
                        </span>
                      </span>
                      <MaterialIcon
                        name="chevron_right"
                        className={isSelected ? "text-[#2563eb]" : "text-[#a4b2c5]"}
                      />
                    </button>
                  );
                })}
              </nav>
            )}

            <div className="mt-5 rounded-[18px] border border-[#d8e6fb] bg-[#edf5ff] p-4">
              <div className="flex items-start gap-3">
                <SafetyCertificateOutlined className="mt-0.5 text-[#2563eb]" />
                <div>
                  <p className="text-sm font-bold text-[#244a7c]">密钥安全保存</p>
                  <p className="mt-1 text-xs leading-5 text-[#607a9e]">
                    密钥由后端加密保存，页面不会回显明文。
                  </p>
                </div>
              </div>
            </div>
          </aside>

          <section className="runtime-service-editor min-w-0 p-5 sm:p-7 lg:p-9">
            {loading && !selectedItem ? (
              <Skeleton active paragraph={{ rows: 10 }} />
            ) : !selectedItem ? (
              <Alert
                type="error"
                showIcon
                message="暂时无法读取服务配置"
                action={<Button onClick={() => void load()}>重试</Button>}
              />
            ) : (
              <>
                <div className="flex flex-wrap items-start justify-between gap-5 border-b border-[#e1e8f2] pb-6">
                  <div className="flex min-w-0 items-start gap-4">
                    <span className="grid h-14 w-14 flex-none place-items-center rounded-[18px] bg-[#e9f1ff] text-2xl text-[#2357b8]">
                      {providerMeta[selectedItem.provider].icon}
                    </span>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Title level={3} className="!m-0 !text-[#17304a]">
                          {providerMeta[selectedItem.provider].title}
                        </Title>
                        {latest ? (
                          <Tag color={statusMeta[latest.status].color}>
                            {statusMeta[latest.status].label}
                          </Tag>
                        ) : (
                          <Tag>未单独配置</Tag>
                        )}
                      </div>
                      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#60738f]">
                        {providerMeta[selectedItem.provider].description}
                      </p>
                      <p className="mt-2 text-xs font-semibold text-[#5272a2]">
                        使用范围：{providerMeta[selectedItem.provider].usage}
                      </p>
                    </div>
                  </div>
                  <div className="rounded-[16px] bg-[#f5f8fd] px-4 py-3 text-right">
                    <p className="text-xs font-semibold text-[#7b8da7]">当前来源</p>
                    <p className="mt-1 text-sm font-bold text-[#17304a]">
                      {sourceLabel(
                        selectedItem.effective_source,
                        scope,
                        Boolean(active),
                      )}
                    </p>
                  </div>
                </div>

                {latest?.validation_error ? (
                  <Alert
                    className="mt-5 rounded-2xl"
                    type="error"
                    showIcon
                    message="上次连接测试未通过"
                    description={latest.validation_error}
                  />
                ) : testedForCurrent ? (
                  <Alert
                    className="mt-5 rounded-2xl"
                    type="success"
                    showIcon
                    icon={<CheckCircleFilled />}
                    message="测试通过，可以应用配置"
                    description="点击“应用配置”后，新启动的任务会使用这一版本。"
                  />
                ) : null}

                <Form
                  form={form}
                  layout="vertical"
                  requiredMark={false}
                  className="mt-7"
                  onValuesChange={() => setTestedRevision(null)}
                >
                  <div className="grid gap-x-5 sm:grid-cols-2">
                    {selectedItem.fields.map((field) => {
                      const meta = fieldMeta[field] ?? {
                        label: field,
                        placeholder: "",
                      };
                      const fullWidth =
                        field === "base_url" || field === "api_key";
                      return (
                        <Form.Item
                          key={field}
                          name={field}
                          label={meta.label}
                          tooltip={meta.hint}
                          className={fullWidth ? "sm:col-span-2" : undefined}
                          rules={[
                            ...(field === "base_url" || field === "api_key"
                              ? [
                                  {
                                    required: true,
                                    message: `请填写${meta.label}`,
                                  },
                                ]
                              : []),
                            ...(field === "model" &&
                            ["llm", "embedding", "tts"].includes(
                              selectedItem.provider,
                            )
                              ? [
                                  {
                                    required: true,
                                    message: "请填写模型或服务标识",
                                  },
                                ]
                              : []),
                          ]}
                        >
                          {field === "dimensions" ||
                          field === "timeout_seconds" ? (
                            <InputNumber
                              className="w-full"
                              min={1}
                              max={
                                field === "timeout_seconds" ? 120 : undefined
                              }
                              suffix={
                                field === "timeout_seconds" ? "秒" : undefined
                              }
                              placeholder={meta.placeholder}
                            />
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
                  </div>
                </Form>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-4 border-t border-[#e1e8f2] pt-6">
                  <div>
                    {active ? (
                      <Button
                        type="link"
                        danger
                        className="!px-0"
                        loading={
                          busyKey === `${selectedItem.provider}:disable`
                        }
                        onClick={() => void restoreDefault()}
                      >
                        恢复部署默认配置
                      </Button>
                    ) : (
                      <p className="text-xs leading-5 text-[#7b8da7]">
                        测试不会影响当前任务；应用后仅对新任务生效。
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      size="large"
                      loading={busyKey === `${selectedItem.provider}:test`}
                      disabled={Boolean(busyKey) && busyKey !== `${selectedItem.provider}:test`}
                      onClick={() => void testConnection()}
                    >
                      测试连接
                    </Button>
                    <Button
                      type="primary"
                      size="large"
                      disabled={!testedForCurrent || Boolean(busyKey)}
                      loading={busyKey === `${selectedItem.provider}:apply`}
                      onClick={() => void applyConfiguration()}
                    >
                      应用配置
                    </Button>
                  </div>
                </div>
              </>
            )}
          </section>
        </div>
      </main>
    </AppSurface>
  );
}
