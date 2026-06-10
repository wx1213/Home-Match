/// App 环境配置（P2-1 引入）。
///
/// 所有配置通过 `--dart-define=KEY=VALUE` 编译时注入，无运行时配置（无 .env 文件依赖）。
///
/// ## 用法
///
/// 开发（默认）：
/// ```bash
/// flutter run -d <device>
/// ```
/// 默认 base URL = http://localhost:8000，dev login 启用
///
/// 指向测试环境：
/// ```bash
/// flutter run -d <device> \
///   --dart-define=API_BASE_URL=https://test-api.homematch.com \
///   --dart-define=ENV_NAME=staging
/// ```
///
/// 生产构建（关闭 dev login）：
/// ```bash
/// flutter build apk --release \
///   --dart-define=API_BASE_URL=https://api.homematch.com \
///   --dart-define=ENABLE_DEV_LOGIN=false \
///   --dart-define=PRODUCTION=true
/// ```
///
/// ## 注意事项
///
/// - `String.fromEnvironment` / `bool.fromEnvironment` 是**编译时常量**，
///   改值后必须重新编译才能生效
/// - 不要把敏感信息（密钥/token）放这里 — 会被打包进二进制
/// - 生产环境务必设置 `PRODUCTION=true` + `ENABLE_DEV_LOGIN=false`，
///   避免 dev 切换器暴露给真实用户
library;

class AppEnv {
  AppEnv._();

  // ============== 必填（生产必须覆盖）==============

  /// 后端 API base URL
  ///
  /// dev 默认 `http://localhost:8000`
  /// 生产必须覆盖（CI/CD 注入真实域名）
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  // ============== 环境标识 ==============

  /// 环境名：development / staging / production
  static const String envName = String.fromEnvironment(
    'ENV_NAME',
    defaultValue: 'development',
  );

  /// 是否生产环境（用于埋点上报、错误监控分流等）
  static const bool isProduction = bool.fromEnvironment(
    'PRODUCTION',
    defaultValue: false,
  );

  // ============== Dev 模式开关（P2-3）==============

  /// 是否启用 dev 自动登录 + dev 切换器
  ///
  /// dev 默认 true（方便本地调试）
  /// 生产必须设 false（避免真实用户看到 🐛 切换器）
  static const bool enableDevLogin = bool.fromEnvironment(
    'ENABLE_DEV_LOGIN',
    defaultValue: true,
  );

  // ============== 调试辅助 ==============

  /// 是否在日志里打印 dev 模式相关信息
  /// （不影响功能，仅日志冗余）
  static const bool verboseDevLog = bool.fromEnvironment(
    'VERBOSE_DEV_LOG',
    defaultValue: false,
  );

  /// 当前模式的人类可读描述（用于 About 页 / 启动横幅）
  static String get summary {
    const dev = enableDevLogin ? ' [DEV]' : '';
    return '$envName ($apiBaseUrl)$dev';
  }
}
