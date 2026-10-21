"""Native rendering contract. Trusted SDK owns actions; generated code only paints state."""
import json


def integration(manifest):
    return '''
【分步实验协议 v2，优先于上面的旧版操作与步骤要求】
宿主提供 window.EduGuidance。你只负责原生视觉绘图，按钮、配置、反馈与教学规则由 SDK 生成。
请生成完整原生 HTML，保持清晰的原生风格和丰富的图表，主体只有一个 simulation-panel：
不生成页面总标题、副标题或开场介绍，宿主已有标题；可保留一个简短“可视化模拟”小标题。
1. 先放 canvas（桌面和手机均至少560 CSS px高度，按DPR绘制），可以增加图例与结果指标。
2. 下方依次放 <div data-guidance-feedback></div>、<div data-guidance-controls></div>、<details data-guidance-history></details>。
不要生成额外的步骤目录、按钮、输入框、自动播放循环、算法实现或自定义完成判断。
在 DOM 就绪后调用一次 EduGuidance.register({render(model, context){...}})。
render 是纯绘图：只读取 model，不能修改模型或调用 dispatch/report；窗口尺寸变化时用最近一次 model 重绘。
容器宽度变化时通过 ResizeObserver 重绘；canvas.width/height 为CSS尺寸乘DPR，每次绘图重设 transform。
排序模型字段：array（当前数组）、initial（初始数组）、phase（select/scan/place/range/done）、selected（选中基准索引，可能-1）、lo/hi（当前区间闭边界）、scan（扫描索引）、boundary（左区间边界）、pivot（基准值）、stack（待处理区间列表）、comparisons/swaps（实际计数）。
排序坐标范围必须包含0：使用min(0,全部值)与max(0,全部值)计算跨度；禁止用maxValue-minValue直接缩放全正数或全负数柱高，避免超出画布。窄屏元素较多时采用可辨认的分行布局，标签至少13px。
排序绘图必须按 array 的当前顺序，支持负数与重复值，标注每个实际值，突出 selected 与 scan（scan仅在phase=scan时高亮），并展示比较及交换次数。不要根据phase自行改变数组。
物理模型字段：mu（动摩擦系数）、velocity（初速度m/s）、time（运行时间s）、distance（当前位移m）、phase（ready/moving/done）、baseline（上一轮停车距离）。
物理图中的基线标签、参数、理论停车标签与小车必须错开，窄屏将参数或说明移至DOM指标，不缩小字号或把文字压在小车上。
物理图示为水平面小车在恒定滑动摩擦下的运动，g=9.8；当前速度=max(0,velocity-mu*9.8*time)，停车距离=velocity²/(2*mu*9.8)。用小车、刻度与清晰指标展现真实状态，模型运行由SDK负责。
可选画布点击仅使用 EduGuidance.dispatch('select',索引)，此调用由SDK做权限校验。不直接写模型或数组。
此份教学规格不可改写：
''' + json.dumps(manifest,ensure_ascii=False)
