# ToneDown

[![ci](https://github.com/ziziphus-jujuba-zao/tonedown/actions/workflows/ci.yml/badge.svg)](https://github.com/ziziphus-jujuba-zao/tonedown/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**尺度你来定。** 面向评论、弹幕、发帖的多语言文本安全分级：0 到 4 五档，从**安全**到**危险**，每个类别单独给概率，
再由策略变成平台侧的「通过 / 需审核 / 拦截」或用户侧的「显示 / 打码 / 隐藏」。判定引擎是
[Jev](https://typesafe.ai)，附带离线词表兜底和实验性的本地 Qwen3Guard 后端。

平台选策略，用户拉滑块，引擎只负责量。

| 线 | 目录 | 状态 |
|---|---|---|
| 引擎，Python 库和命令行 | `packages/core` | 可用 |
| 平台侧 API，FastAPI 和 Docker | `packages/server` | 可用 |
| 用户端屏蔽，B 站和 YouTube 的油猴脚本 | `extension/userscript` | MVP，页面选择器还没在真实浏览器里验证 |
| MV3 浏览器扩展 | `extension/mv3` | 计划中 |

## 快速开始

```bash
git clone https://github.com/ziziphus-jujuba-zao/tonedown.git && cd tonedown
cp .env.example .env            # 填入 Jev 的 key；不填就只用离线词表
uv sync --all-packages

uv run tonedown grade "楼主就是个傻X" "Great episode!" "お前の住所知ってるからな"
uv run tonedown-server         # http://127.0.0.1:8080/docs
uv run eval/run_eval.py         # 金标集上的分语言成绩表
```

然后用 Tampermonkey 或 Violentmonkey [一键安装油猴脚本](https://raw.githubusercontent.com/ziziphus-jujuba-zao/tonedown/main/extension/userscript/tonedown.user.js)，打开 B 站或 YouTube 视频页，
点右下角圆形的 **TD** 按钮拉滑块。

## YouTube 能用吗

能。评论区和直播聊天都有适配器。评论走 `ytd-comment-view-model` 节点，直播聊天在 `/live_chat`
的 iframe 里单独运行一份脚本。选择器按 2026 年 9 月的页面结构写，还没有在真实浏览器里验证过，
页面改版就到 `extension/userscript/tonedown.user.js` 里改对应的 `sweep()`。

## 分级

| 等级 | 名称 | 例子 |
|---|---|---|
| 0 | 安全 | 观点、玩笑、对作品的尖锐差评 |
| 1 | 轻微 | 语气粗鲁、轻度脏话、灌水 |
| 2 | 中度 | 针对个人的辱骂、诈骗或广告、下流的性暗示 |
| 3 | 严重 | 仇恨言论、涉及未成年或非自愿的性内容、美化暴力、人肉、卖药卖枪 |
| 4 | 危险 | 可信的暴力威胁、表达或鼓励自杀自伤、教人作恶 |

类别：广告、辱骂、仇恨、色情、暴力、自伤、违法，另有「是否针对具体个人」的标记。

## 2026-09-19 的实测

金标集 63 条手写评论，11 种语言（中、英、日、韩、西、俄、阿、德、法、越、印地），rubric 用英文，
Jev `jev-latest`，策略 `balanced`，命令 `uv run eval/run_eval.py --backend jev`：

| 等级全对 | 误差一档内 | F1（等级 ≥ 2） | 类别 | 针对个人 | 误拦 | 漏拦 |
|---|---|---|---|---|---|---|
| 63 / 63 | 63 / 63 | 1.00 | 63 / 63 | 62 / 63 | 0 | 0 |

样本包含 nmsl、sb 这类拼音缩写，yyds 这类长得像骂人其实是夸的黑话，以及 傻β 这类同形字。
完整的九个问题下每条评论 520 到 580 个输入 token，缓存前每千条约 0.02 美元，打包后每条 20 到
200 毫秒。非中英文的威胁落在 3.2 到 3.8 而不是 3.9，所以策略以等级 3 及以上触发。这么小的集合
只能证明流水线通了，不能证明模型：上线前先把 `eval/golden` 扩大再定阈值。

## 隐私

屏蔽模式发出去的是别人的公开评论，自查模式发出去的是你自己的草稿，本地模式零外发。服务器只存
哈希和概率，不存文本。详见 `docs/PRIVACY.md`。

## 许可证

Apache-2.0。架构、API、适配器、路线图见 `docs/`。
