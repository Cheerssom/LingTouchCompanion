# agent/native — 对话 agent 与语音（对话 agent 同学）

本次只放接口，没有实现：

- `include/lingtouch/agent/speech.h`：语音识别、语音合成。实现计划用 sherpa-onnx（官方支持鸿蒙和安卓，离线，C API）。录音和放音只能用平台接口，留在 App 外壳里，外壳把 PCM 交给这里。
- `include/lingtouch/agent/agent.h`：对话 agent。

语言模型接口在 `core/include/lingtouch/inference.h`（`LanguageModel`），与 SpatialLM 的语言部分共用，实现用 llama.cpp。

导航、命令解析的 Node.js 服务在 [`../backend`](../backend/README.md)。
