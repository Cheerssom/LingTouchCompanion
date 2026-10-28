// Kotlin（com.lingtouch.companion.NativeCore）↔ 核心。只做转换，不放业务逻辑。
#include <jni.h>

#include <cstdio>
#include <memory>
#include <mutex>
#include <string>

#ifdef __ANDROID__
#include <android/log.h>
#endif

#include "lingtouch/config.h"
#include "lingtouch/engine.h"
#include "lingtouch/perception/cs30_libusb_source.h"
#include "lingtouch/perception/pipeline.h"
#include "lingtouch/report_json.h"

using namespace lingtouch;

namespace {

void log_line(const std::string& message) {
#ifdef __ANDROID__
  __android_log_print(ANDROID_LOG_INFO, "LingTouchCore", "%s", message.c_str());
#else
  std::fprintf(stderr, "[LingTouchCore] %s\n", message.c_str());
#endif
}

struct NativeState {
  std::unique_ptr<Engine> engine;
  std::mutex camera_mutex;
  std::unique_ptr<Cs30LibusbSource> camera;
  std::mutex error_mutex;
  std::string last_error;

  void set_error(const std::string& e) {
    std::lock_guard<std::mutex> lock(error_mutex);
    last_error = e;
  }
};

NativeState* state(jlong handle) { return reinterpret_cast<NativeState*>(handle); }

jstring to_jstring(JNIEnv* env, const std::string& s) { return env->NewStringUTF(s.c_str()); }

std::string& create_error() {
  static std::string e;
  return e;
}

}  // namespace

extern "C" {

JNIEXPORT jlong JNICALL Java_com_lingtouch_companion_NativeCore_nativeCreate(JNIEnv*, jclass) {
  Result<Config> config = default_config();
  if (!config) {
    create_error() = "默认参数有误：" + config.error();
    log_line(create_error());
    return 0;
  }
  auto* s = new NativeState();
  s->engine = std::make_unique<Engine>(config.value());
  return reinterpret_cast<jlong>(s);
}

JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativeCreateError(JNIEnv* env, jclass) {
  return to_jstring(env, create_error());
}

JNIEXPORT void JNICALL Java_com_lingtouch_companion_NativeCore_nativeDestroy(JNIEnv*, jclass, jlong handle) {
  NativeState* s = state(handle);
  if (s == nullptr) return;
  {
    std::lock_guard<std::mutex> lock(s->camera_mutex);
    s->camera.reset();
  }
  delete s;
}

// 返回 null 表示成功，否则是错误说明。fd 来自 UsbDeviceConnection.getFileDescriptor()，由 Kotlin 侧关闭。
JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativeOpenCamera(JNIEnv* env, jclass, jlong handle,
                                                                                   jint fd) {
  NativeState* s = state(handle);
  std::lock_guard<std::mutex> lock(s->camera_mutex);
  s->camera.reset();
  Result<std::unique_ptr<Cs30LibusbSource>> source = Cs30LibusbSource::open_fd(fd, s->engine.get(), log_line);
  if (!source) return to_jstring(env, source.error());
  Status started = source.value()->start();
  if (!started) return to_jstring(env, started.message);
  s->camera = std::move(source.value());
  return nullptr;
}

JNIEXPORT void JNICALL Java_com_lingtouch_companion_NativeCore_nativeCloseCamera(JNIEnv*, jclass, jlong handle) {
  NativeState* s = state(handle);
  std::lock_guard<std::mutex> lock(s->camera_mutex);
  s->camera.reset();  // 停流、release；fd 由 Kotlin 侧随后关闭
}

JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativeResetCamera(JNIEnv* env, jclass, jlong handle) {
  NativeState* s = state(handle);
  std::lock_guard<std::mutex> lock(s->camera_mutex);
  if (!s->camera) return to_jstring(env, "相机没有打开");
  Status r = s->camera->reset_device();
  return r ? nullptr : to_jstring(env, r.message);
}

JNIEXPORT jboolean JNICALL Java_com_lingtouch_companion_NativeCore_nativeCameraStreaming(JNIEnv*, jclass,
                                                                                         jlong handle) {
  NativeState* s = state(handle);
  std::lock_guard<std::mutex> lock(s->camera_mutex);
  return s->camera && s->camera->streaming() ? JNI_TRUE : JNI_FALSE;
}

JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativeGridJson(JNIEnv* env, jclass, jlong handle) {
  return to_jstring(env, grid_json(state(handle)->engine->latest_grid(), monotonic_now_ns()));
}

JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativeStatsJson(JNIEnv* env, jclass, jlong handle) {
  return to_jstring(env, stats_json(state(handle)->engine->stats()));
}

JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativeDeviceSummary(JNIEnv* env, jclass,
                                                                                      jlong handle) {
  return to_jstring(env, state(handle)->engine->device_summary());
}

// 0 = 配置里没设定（待 Hsinlung 定），1 = flat，2 = raised
JNIEXPORT jint JNICALL Java_com_lingtouch_companion_NativeCore_nativeConfigUnknownPolicy(JNIEnv*, jclass,
                                                                                         jlong handle) {
  const auto& p = state(handle)->engine->config().tactile.unknown_cell_policy;
  return p ? static_cast<jint>(*p) : 0;
}

JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativeConfigText(JNIEnv* env, jclass, jlong handle) {
  return to_jstring(env, format_config(state(handle)->engine->config()));
}

// 最新栅格 → 15 字节旧板帧。policy 必须是 1（flat）或 2（raised），否则返回 null，原因见 nativeLastError。
JNIEXPORT jbyteArray JNICALL Java_com_lingtouch_companion_NativeCore_nativeEncodeLatest(JNIEnv* env, jclass,
                                                                                        jlong handle, jint policy) {
  NativeState* s = state(handle);
  Result<LegacyFrame> f = s->engine->encode_legacy(s->engine->latest_grid(), static_cast<UnknownCellPolicy>(policy));
  if (!f) {
    s->set_error(f.error());
    return nullptr;
  }
  jbyteArray out = env->NewByteArray(kLegacyFrameBytes);
  env->SetByteArrayRegion(out, 0, kLegacyFrameBytes, reinterpret_cast<const jbyte*>(f.value().data()));
  return out;
}

JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativeLastError(JNIEnv* env, jclass, jlong handle) {
  NativeState* s = state(handle);
  std::lock_guard<std::mutex> lock(s->error_mutex);
  return to_jstring(env, s->last_error);
}

// 对最近一帧做平面检查（对着平整的墙或斜看地面时用）
JNIEXPORT jstring JNICALL Java_com_lingtouch_companion_NativeCore_nativePlaneCheck(JNIEnv* env, jclass, jlong handle) {
  Engine& e = *state(handle)->engine;
  DepthFrame frame;
  if (!e.latest_frame(&frame)) return to_jstring(env, "还没有收到帧");
  const std::optional<CameraIntrinsics> in = e.intrinsics();
  if (!in) return to_jstring(env, "没有可用内参");
  return to_jstring(env, format_plane_check(check_planarity(frame, *in, e.config().depth, 0.5)));
}

}  // extern "C"
