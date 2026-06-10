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
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
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
  // 启动自动登录（开发模式用 _currentDevCode）：
  // - 优先用上次保存的 dev code（让用户切身份后能继续）
  // - 兜底用 _currentDevCode（首次安装 / 清存储后）
  final container = ProviderContainer();
  final storage = container.read(secureStorageProvider);
  final savedCode = await storage.read(key: 'last_dev_code');
  if (savedCode != null && savedCode.isNotEmpty) {
    _currentDevCode = savedCode;
  }
  // 总是尝试自动登录（dev 模式无 token 也能用 mock 登录）
  await _doLogin(container, _currentDevCode);
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
Future<void> switchDevUser(ProviderContainer container, String code) async {
  await _doLogin(container, code);
}
