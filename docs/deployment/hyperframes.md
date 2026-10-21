# HyperFrames 原生课堂

课堂资源仍使用 `classroom` 类型、原资源 ID 和版本；新内容为 `hyperframes/v1`。完整上游位于 `vendor/hyperframes`，固定提交见 `hyperframes-runtime/PROVENANCE.md`，平台适配在 `backend/src/app/integrations/hyperframes`，不修改上游。CLI 与保留的原生播放器依赖固定为 0.8.168；学习页面直接播放原生流程导出的 MP4。

## 安装与启动

使用 Node 22+、Python 3.12、FFmpeg/ffprobe。Linux worker 安装 `bubblewrap` 与 Chromium 系统依赖，然后运行 `scripts/install-all.sh`。运行 `python scripts/check-hyperframes.py` 检查依赖。原生运行时使用 `npm --prefix hyperframes-runtime ci`；前端沿用 pnpm 锁文件。

`HYPERFRAMES_BROWSER_PATH` 可指定已安装 Chromium 的可执行文件；未指定时使用 `hyperframes browser ensure` 安装的原生浏览器缓存。`HYPERFRAMES_BWRAP_PATH` 只用于非标准 bubblewrap 安装位置。生成任务缺少隔离运行时会明确失败，不能降级为无隔离执行。Windows 可开发前端；生成 worker 运行于 Linux。

无需启动课堂 sidecar。后端通过原生 CLI 执行 lint/check/render。发布时更新后端依赖、构建前端、更新后端 systemd unit，再按运维流程重启。旧 `edu-ai-openmaic` 服务应在新课堂验收后停止并禁用；本次源码迁移不会自动删除生产文件或停服务。

## 数据与接口

工程写入 `COURSE_STORAGE_ROOT/hyperframes/projects/<id>/<digest>`；配音缓存与持久任务检查点在同级目录。备份必须覆盖整个 `COURSE_STORAGE_ROOT/hyperframes`。工程清理需要引用检查，不能仅按创建时间删除旧版本。

平台负责需求理解、资料研究、学习路径和每个节点的学习目标，再将该节点的目标、依据、受众和用户明确的媒体要求交给视频生成器。通用 Agent 加载完整原生路由与工作流，由 HyperFrames 制作 BRIEF、讲稿、分镜、画面、动画，调用原生音频脚本、组装、截图检查和渲染。现有中文语音通过原生 `HF_MEDIA_ENGINE` 扩展接入；平台不预写讲稿或替代原生创作逻辑。用户未要求的讲义、习题、自测和固定场景数不自动添加。

原生工作目录保存在 `COURSE_STORAGE_ROOT/hyperframes/workflows/<request-digest>`，包含恢复所需的工程及 `.host` 执行记录。失败重试会继续原生已有文件；原生渲染完成后导入失败只重试导入。原仓库和运行库以只读方式挂载，工程可写；创作命令允许网络以获取原生所需素材，成品资源必须本地化。宿主 Agent、原生分镜工作者和命令共用任务取消与执行窗口。

场景派发优先使用 `dispatch_frames`，程序从原生任务包清单读取准确路径，将完整 `_role.md`、frame packet、frame.md 和公共素材说明交给场景作者；通用异步 `run_workers` / `run_worker` 保留。通过 `poll_workers` 收取状态。讲稿、配音时长和公共素材准备好后派发全部独立场景，队列自动分批，场景完成后仍由原生主 Agent 验证、组装和渲染。默认每个视频 4 个场景 worker，由 `HYPERFRAMES_FRAME_CONCURRENCY` 调整；同一后端进程最多 8 个，由 `HYPERFRAMES_GLOBAL_FRAME_CONCURRENCY` 调整。课程资源默认并发为 4，由 `COURSE_PREPARATION_RESOURCE_CONCURRENCY`（1–32）调整；多进程部署时应按进程数核算总容量。这些配置在进程启动时读取，正在运行的原生会话保留已加载的实现。

`prepare_scene_assets` 将旁白型原生流程的音频生成、实测时长同步、音效、字幕和任务包生成连续交给原仓库脚本执行，输出 `.hyperframes/host-scene-assets.json`（准确文件路径与各步骤耗时）。讲稿/分镜仍由原生 Agent 创作；非旁白工作流可以继续调用原生脚本。原生 SCRIPT.md 的 `(Frame N)` 标题及缩进讲稿格式在调用配音前检查，避免无声空结果。运行中的相同准备任务返回同一个命令；同项目相同文本的并行配音合并，修改后的文本独立生成，旧成品不覆盖。`poll_command` 与 `poll_workers` 在宿主内最多等待 45 秒并持续检查取消，减少模型轮询；上游仓库未裁剪或修改。

`render_project` 使用原生 CLI 高质量输出，默认 `HYPERFRAMES_RENDER_WORKERS=2`，保留 CLI 对小内存主机的自动安全模式。设为 1 可显式恢复低内存单 worker 模式。当前沙箱仍用软件图形渲染及逐帧截图，没有未经验证地启用 GPU。相同 65.33 秒成片的隔离串行对照，单 worker 260.58 秒、双 worker 160.63 秒，约减少 38.4%；分辨率/帧率/时长一致、音视频解码通过，每 10 秒抽帧 SSIM 为 1。此结果只代表该段渲染，不代表整课同等提速；同期云端配音切换属于独立变更。源码更新须重载后端和补充 worker，发布状态见 `docs/acceptance/2026-10-19-hyperframes-speed/deployment.json`。

2026-10-19 已增加用户级 `edu-ai-durable-workers.service`，与主后端共享 PostgreSQL 队列和原子租约。当前主后端提供 3 个通用工作线程和 2 个专用 `preparation_step` 调度线程，新增服务提供 5 个生成线程；长任务不会占用专用调度线程。主后端 `.env` 设置 `DURABLE_JOB_CONTROL_WORKERS=2`，新增服务通过命令行显式指定 `--workers 5 --control-workers 0`。2026-10-19 配音并行发布将专用调度移到主后端，让补充服务排空旧任务时仍能调度新课程；补充服务排空后加载新参数，总容量保持 8 个普通线程加 2 个专用调度线程。未安装新增服务的单进程部署可使用默认 `DURABLE_JOB_CONTROL_WORKERS=2`。`DURABLE_JOB_WORKERS` 仍表示普通工作线程数，专用调度线程额外计数。超过容量的任务仍会排队。

用户服务模板位于 `deploy/systemd/edu-ai-durable-workers.service`，安装到 `~/.config/systemd/user/` 后执行 `systemctl --user daemon-reload` 和 `systemctl --user enable --now edu-ai-durable-workers`。当前账号已启用 linger，退出登录后继续运行。查看状态使用 `systemctl --user status edu-ai-durable-workers` 和 `journalctl --user -u edu-ai-durable-workers`。新增服务加入运行中的队列时不执行主服务启动修复；正常停止会停止领取并等待已领取任务完成，最多一小时，不应直接强杀。移除服务前先排空其任务，并确认主后端保留 2 个专用调度线程。

每个场景有独立的 `.host/worker-tmp/<worker-id>`，在其 shell 中挂载为 `/tmp`，避免截图、测试脚本和临时端口文件互相覆盖。`start_preview` 启动沙箱内的本地预览服务，由操作系统绑定空闲端口，避免并发 worker 抢占同一个固定端口；服务随 worker 清理。项目目录仍共享，原生契约要求 worker 只修改自己负责的场景，公共素材、分镜和组装由主 Agent 持有。`.host/workers/<id>.json` 记录排队、运行、完成、失败和取消状态；工具事件带 worker_id。成功通知不是产物验收，父 Agent 必须核对实际文件。主任务退出会取消队列，运行中的 worker 共用取消和剩余执行窗口；失败场景单独重派，成功场景不必重做。工作状态记录用于审计，进程重启后由原生文件和分镜状态恢复，不把旧 running 记录冒认成仍在运行的 future。

宿主提供精确文本替换 `edit_file`。模型调用未挂载工具时，适配层在执行整批工具前要求模型按实际工具列表纠正，最多两次；耗尽后保留明确的模型响应错误，而不是让不存在的工具执行。新调度代码需要后端重新加载才生效，运行中的旧 Agent 不能仅靠修改文件原地切换。

交付阶段读取原生 STORYBOARD、SCRIPT、audio_meta 和实际 composition 时间，保存完整工程、MP4、段落级 SRT 与播放时间轴。语音服务暂不提供逐词时间戳，不虚构字级对齐。媒体导入回执表示 ffprobe 与时间轴结构校验通过，不冒称教学内容审核。历史平台 JSON 讲稿/HTML 生成、visible_targets 注入和固定次数修复不再参与新生产链路。旧 `HYPERFRAMES_STRICT_VISUAL_CHECKS`、`HYPERFRAMES_REPAIR_ATTEMPTS` 不控制新链路。

2026-10-19 工具与职责调整：用户要求以稳定生成和播放为准，不反复检查。场景 worker 保留完整原生角色、分镜包与动画规则，只编写负责的场景、进行一次文件结构自检，再交给主流程；不再向它公开图片检查和预览工具，也不再要求它自行准备字体、启动浏览器或编写截图脚本。主流程仍保留原生脚本、模板、并发派发、组装、字幕、截图交付和渲染能力。工具列表与提示词限定默认职责，shell 不使用命令黑名单，完整上游仓库不裁剪。

安装时执行 `python scripts/prepare-hyperframes-runtime.py`（已接入两套 install-all 脚本），按固定 SHA256 缓存完整 Noto Sans SC 可变字体及 OFL 许可证到 `hyperframes-runtime/assets/fonts/`。主流程 `prepare_project` 在原生 init 后把字体和本地 GSAP 放入项目，返回可直接放入原生模板的字体声明；组装后再次调用可将原生 index 的已知 GSAP CDN 引用本地化。无需任务内下载字体、探查字形或猜测 Puppeteer/fontkit/sharp 内部入口；主流程诊断使用现有 `start_preview` 和原生 snapshot。

主流程 `check_project` 在合成后调用一次原生 `hyperframes check --json`（已含 lint），仅 lint/runtime/motion 失败阻塞，layout/contrast 结果保存但不触发美化返工。浏览器跳过或报告不完整不能算通过。结果按工程输入内容和工具版本摘要缓存，文件未变时复用；实际失败只修对应场景，内容变更后再检查。保留一次原生场景中点联系表作为交付，不默认调用视觉模型，不在渲染后再次检查。媒体流与时间轴仍由导入阶段验证。此轮不调整配音队列，也不声称解决了已有 TTS 429 问题。

课堂持久任务的新建和重试统一使用至少 3600 秒的排队窗口和执行窗口，执行窗口从 worker 领取任务时重新计时；保留标准资源批次已有的更长排队窗口。旧课堂遗留的 300 秒期限不足以覆盖原生复检和渲染，重试时也会升级，用户主动取消仍立即生效。

需要管理员激活已验证的后端改动时，执行 `sudo /home/zxqs_ep/Edu_AI/scripts/deploy-hyperframes-service.sh`。脚本备份旧 unit，移除旧 sidecar 依赖，重启后端，确认 API 恢复后停用旧 OpenMAIC 服务。前端发布与端到端测试结果另见对应发布记录；源码修改本身不代表正在运行的后端已更新。

播放会话接口：`POST /api/self-learning/courses/{course}/materials/classroom/{id}/versions/{version}/playback`。返回一小时有效的工程和导出链接。每次取文件重新验证课程权限、资源版本及工程摘要。学习页面使用浏览器视频控件播放该版本的 MP4（画面与配音已合成），继续使用原时间轴进行跳转、进度与提问定位，不在学习页重新加载原生 HTML。工程下载和原生工具能力保留。原生 HTML 资源端点仍使用 opaque sandbox；音频播放需要浏览器用户手势。

2026-10-19 复现 SSH 转发端口播放故障：线上 Nginx 的 `Host $host` 丢失外部端口，服务端生成的原生 HTML CSP 与浏览器实际来源不符，脚本与配音均被拦截。学习端切换为 MP4 后不再依赖这条 HTML 加载链，前端已单独发布，无后端重启。仓库 `deploy/nginx/edu-ai.conf` 已改用 `$http_host`；系统 Nginx 配置尚未同步，后续需要原生 HTML 在线预览时应由管理员部署该配置并检查、reload。不得将源文件修改当作线上代理已经更新。

学习问题提交 `{kind:hyperframes, seconds, segment_id?, content_hash?}`；classroom 快照携带 `position`。服务端从授权版本解析当前段落、相邻讲稿、画面描述和事件，不信任客户端提交的讲稿。定位器保留在问题快照和引用中，刷新和跳转不会改变历史问题。

## 播客与视频配音并行（2026-10-19）

播客整节通过 `PODCAST_AUDIO_CONCURRENCY=8` 并行提交；原生视频 `audio.mjs → HF_MEDIA_ENGINE → workflow_audio` 按 `HYPERFRAMES_AUDIO_CONCURRENCY=8` 并行提交各场景完整讲稿。输出按原章节/场景顺序汇总，取消会停止排队请求，完成缓存仍保留。原生视频后续路径为时长同步、场景画面并发制作、主流程检查、合成渲染、媒体导入。

本地 Qwen TTS 用一个共享队列合并独立请求，`QWEN_TTS_REQUEST_BATCH_SIZE=4`、`QWEN_TTS_BATCH_MAX_CHARS=1600`、`QWEN_TTS_MAX_PENDING=64`。模型语音 token 推理实际批处理，波形解码逐条完整处理以控制显存；七节实测分成 4+3 两批。每段原文完整输入，不插入断句，不截断，不限制总篇幅；单次输入上限仍为 1500 字。批次失败会缩小完整请求组重试，不拆原文。长篇本地请求最长等待 3600 秒，覆盖排队与推理；队列满才返回 429。

本机正式入口为 `TTS_API_BASE=http://127.0.0.1:8191/v1`，用户级 `edu-ai-tts-batch.service` 使用 GPU 1；模板在 `deploy/systemd/edu-ai-tts-batch.service`，已启用 linger 和开机启动。原系统服务 8188/GPU 0 保留供发布前在途视频使用，不能在旧调用结束前停止。此处 `/usr/bin/env` 在 ExecStart 中覆盖设备参数，避免 EnvironmentFile 中旧值覆盖 GPU 选择。通用单服务安装仍可使用 8188，只需其服务加载新实现并配置调用地址。

真实相同七节共 2175 字，配音与合并耗时 383.95 秒；此前生产完整任务 911.10 秒包含少量写稿/保存开销，因此 2.37 倍仅为本次观测，不是严格同条件性能保证。四场景原生音频链验证同一批次、顺序与时长同步，输出媒体全部解码通过；没有在本轮重跑完整 AI 视频创作或逐字听校。证据见 `docs/acceptance/2026-10-19-tts-concurrency/`。

## 稳定配音（2026-10-19）

当前本地 TTS 使用 `stable-narration-v1`。选定的说话人保持不变，所有章节/场景统一使用平稳讲解风格，服务端不接受逐场景提示词重新塑造声线。主生成器使用按文本、音色、语言派生的独立随机序列，temperature=0.65、top_k=30、top_p=0.9；声音细节生成器使用确定性选择。随机状态不随同批请求的顺序共享，但 GPU 数值差异仍可能让不同批次的最终波形不完全相同，不能承诺逐采样点一致。纯贪心主生成器实测耗时异常，已否决，未发布。

当前系统 Vivian 音色增加整段音高中心校准：目标 240 Hz，单次调整不超过 3 个半音，保留句内自然抑扬；使用 Rubber Band 的 formant=preserved 保留共振峰。其他音色尚无校准参考，不套用 Vivian 的目标。`QWEN_TTS_PITCH_FFMPEG` 默认 `/usr/bin/ffmpeg`，要求编译了 rubberband 滤镜，启动时检查；本机 conda FFmpeg 没有此滤镜，不能替代。分析和校准不切分讲稿，不取消现有 GPU 批处理。响应提供 `X-Voice-Profile`、`X-Voice-ID`，健康接口显示当前 profile。

共享 narration 与视频音频缓存版本已更新，防止新任务复用旧风格文件；已发布的播客/视频不会自动改写。真实四场景处理前音高中位数 214.60–267.27 Hz，处理后 238.11–245.09 Hz；另含重复文本和 237 字段落，共 8 段校准与解码验证通过。音高指标不能代表说话人相似度或逐字正确率，没有冒称人工听校。证据见 `docs/acceptance/2026-10-19-stable-voice/`。

## 保留的原生能力与历史数据

上游 CLI、Studio、SDK、模板、registry、skills、文档和示例完整保留；默认产品接入完整原生创作工作流、检查和渲染流程，学习播放使用导出的 MP4。需要原生创作工具时可在开发环境直接使用固定版本 CLI；不把无鉴权 Studio 公开到生产。

历史 OpenMAIC 数据不自动改写；课堂页面显示文本与已有媒体归档。重新生成可得到原生动画课堂。新课堂导出工程 ZIP、MP4、SRT，旧 PPTX 渲染链不再参与。历史源码和测试仅用于归档兼容，不能作为新生成入口。资料修改会重新生成同步的工程、配音与时间轴，保留原文档。

## 验收

运行 `PYTHONPATH=backend/src python -m pytest backend/src/tests/hyperframes -q`，以及前端 HyperFrames 定位/桥接测试、类型检查和构建。浏览器验收覆盖实际导出视频、音频手势与非零音频采样、跳转、速度、精确时间引用、暂停恢复和移动端，并通过非默认转发端口访问。`frontend/scripts/check-hyperframes-video-online.mjs` 使用真实已导入演示课程及真实 API；旧原生 iframe 验收脚本仅对应历史播放实现。真实模型/TTS的结果与固定测试夹具证据分别记录，不能互相替代。
