// 语音识别与合成接口（本次只定接口，不集成库）。
// 实现计划用 sherpa-onnx：官方支持鸿蒙和安卓，离线，有 C API。
// 录音、放音本身只能用平台接口，留在 App 外壳里；外壳把 PCM 交给这里。
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "lingtouch/result.h"

namespace lingtouch {
namespace agent {

struct AudioFormat {
  int sample_rate_hz = 16000;
  int channels = 1;
};

struct RecognitionResult {
  std::string text;
  bool is_final = false;
};

class SpeechRecognizer {
 public:
  virtual ~SpeechRecognizer() = default;
  virtual Status load(const std::string& model_dir) = 0;
  // 流式送入 16-bit PCM；返回到目前为止的识别结果
  virtual Result<RecognitionResult> accept(const int16_t* pcm, size_t samples, const AudioFormat& format) = 0;
  virtual void reset() = 0;
};

class SpeechSynthesizer {
 public:
  virtual ~SpeechSynthesizer() = default;
  virtual Status load(const std::string& model_dir) = 0;
  // 返回 16-bit PCM，由外壳播放
  virtual Result<std::vector<int16_t>> synthesize(const std::string& text, double speed, AudioFormat* format) = 0;
};

}  // namespace agent
}  // namespace lingtouch
