/// Home Match APP 入口
///
/// P1-0 修复（2026-06-10）：
/// dev code 跟 user id 关系说明：
/// - dev code 是稳定的 wechat code label（如 `dev_alice`），登录用它调
///   `POST /v1/auth/wechat-login`，后端生成 `mock_unionid_{code[:16]}`，
///   再去 users 表里 find_or_create
/// - user id 由 PostgreSQL SERIAL 序列按创建顺序分配，**与 dev code 里的数字无关**
/// - 所以 `dev_seller_7` 拿到的不一定是 user 7，可能是任何 id
/// - 6 个稳定 dev code 由 `backend/scripts/seed_dev_users.py` 预创建，
///   详见 `docs/05-dev-users.md`
///
/// P2-1/2/3 修复（2026-06-10）：
/// - dev 模式相关功能（自动登录、切换器）受 `AppEnv.enableDevLogin` 守卫
/// - 生产构建必须传 `--dart-define=ENABLE_DEV_LOGIN=false --dart-define=PRODUCTION=true`
/// - API base URL 走 `--dart-define=API_BASE_URL=...`，默认 localhost:8000
library;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/env/app_env.dart';
import 'core/router/app_router.dart';
import 'core/network/dio_client.dart';
import 'features/auth/auth_service.dart';
import 'features/auth/auth_state.dart';

/// 当前 dev code（可被切换）- 启动时使用，登录后从后端 dev-identities 动态获取
///
/// 默认为 `dev_alice`（见 `backend/scripts/seed_dev_users.py` 的稳定 dev user 列表）
String _currentDevCode = 'dev_alice';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // P2-1：启动横幅（仅 debug 模式可见，生产静默）
  if (kDebugMode && AppEnv.verboseDevLog) {
    debugPrint('[HomeMatch] env: ${AppEnv.summary}');
  }

  final container = ProviderContainer();

  // P2-3：dev 自动登录守卫
  // - AppEnv.enableDevLogin = true（默认 dev）：走原自动登录流程
  // - AppEnv.enableDevLogin = false（生产）：跳过，进登录页让用户用真实微信/Apple 登录
  if (AppEnv.enableDevLogin) {
    final storage = container.read(secureStorageProvider);
    final savedCode = await storage.read(key: 'last_dev_code');
    if (savedCode != null && savedCode.isNotEmpty) {
      _currentDevCode = savedCode;
    }
    await _doLogin(container, _currentDevCode);
  } else if (kDebugMode) {
    debugPrint('[HomeMatch] dev login disabled (production build)');
  }

  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const HomeMatchApp(),
    ),
  );
}

/// 内部：用指定 code 登录并写全局状态
Future<void> _doLogin(ProviderContainer container, String code) async {
  try {
    final auth = await container.read(authServiceProvider).loginWithWechat(code);
    final storage = container.read(secureStorageProvider);
    await storage.write(key: 'access_token', value: auth.accessToken);
    await storage.write(key: 'refresh_token', value: auth.refreshToken);
    await storage.write(key: 'last_dev_code', value: code); // 记住用哪个 code 登录
    container.read(authProvider.notifier).login(
          userId: auth.userId!,
          userName: auth.userName!,
          displayName: auth.displayName,
          avatarUrl: auth.avatarUrl,
          creditScore: auth.creditScore,
          accessToken: auth.accessToken!,
          refreshToken: auth.refreshToken!,
        );
    // 关键：登录成功后恢复登录态（防止 401 跳登录后用 dev code 切回被困在登录页）
    container.read(isLoggedInProvider.notifier).state = true;
    _currentDevCode = code;
  } catch (_) {
    // ignore: avoid blocking UI on auto-login failure
  }
}

/// 切换登录用户（暴露给 UI 调用）
///
/// P2-3：生产构建（`AppEnv.enableDevLogin = false`）下 no-op，
/// 防止误调用把生产用户切到 dev 身份。
Future<void> switchDevUser(ProviderContainer container, String code) async {
  if (!AppEnv.enableDevLogin) {
    if (kDebugMode) {
      debugPrint('[HomeMatch] switchDevUser ignored: dev login disabled');
    }
    return;
  }
  await _doLogin(container, code);
}
