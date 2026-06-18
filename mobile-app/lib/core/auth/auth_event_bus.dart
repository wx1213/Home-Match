/// 全局认证事件总线 - 监听 token 过期、强制登出等
library;

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// 认证事件
class AuthEvent {
  /// 401/403 触发的强制登出（token 过期或被踢）
  final bool forceLogout;
  final String? reason;

  const AuthEvent({required this.forceLogout, this.reason});

  static const logout = AuthEvent(forceLogout: true);

  /// C6 引入：登录成功事件（PushService 监听 → 注册 FCM device）
  static const login = AuthEvent(forceLogout: false);
}

/// 全局事件总线（用 ChangeNotifier 实现，让 go_router 也能监听）
class AuthEventBus extends ChangeNotifier {
  AuthEvent? _lastEvent;
  AuthEvent? get lastEvent => _lastEvent;

  void emit(AuthEvent event) {
    _lastEvent = event;
    notifyListeners();
  }
}

final authEventBusProvider = Provider<AuthEventBus>((ref) {
  final bus = AuthEventBus();
  ref.onDispose(bus.dispose);
  return bus;
});

/// 暴露成 Listenable（go_router 的 refreshListenable 接受 Listenable）
final authEventListenableProvider = Provider<Listenable>((ref) {
  return ref.watch(authEventBusProvider);
});
