// 对话 agent 接口（本次只定接口）。语言模型接口在 core 的 lingtouch/inference.h（与 SpatialLM 共用）。
#pragma once

#include <string>
#include <vector>

#include "lingtouch/result.h"

namespace lingtouch {
namespace agent {

struct AgentTurn {
  std::string user_text;
  // 由核心提供的当前状态摘要，例如设备连接、栅格状态；不填编造的值
  std::string context;
};

struct AgentReply {
  std::string speech;                // 要播报的话
  std::vector<std::string> actions;  // 结构化动作，例如 "start_navigation:天安门"
};

class Agent {
 public:
  virtual ~Agent() = default;
  virtual Result<AgentReply> respond(const AgentTurn& turn) = 0;
};

}  // namespace agent
}  // namespace lingtouch
