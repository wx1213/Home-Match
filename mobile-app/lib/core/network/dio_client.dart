/// HTTP 客户端 - dio + 拦截器链

library;
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../auth/auth_event_bus.dart';
import '../env/app_env.dart';
import 'auth_interceptor.dart';

/// API base URL（从 AppEnv 编译时注入，兼容旧代码引用）
///
/// P2-1/2 修复：原硬编码 localhost:8000，现通过 --dart-define=API_BASE_URL=...
/// 在打包时注入。生产环境必须覆盖。
const String kApiBaseUrl = AppEnv.apiBaseUrl;

/// Token 存储（Secure Storage）
final secureStorageProvider = Provider<FlutterSecureStorage>((ref) {
  return const FlutterSecureStorage();
});

/// auth 拦截器 provider - 401 时发事件到全局总线
final authInterceptorProvider = Provider<AuthInterceptor>((ref) {
  final bus = ref.read(authEventBusProvider);
  return AuthInterceptor(
    ref.read(secureStorageProvider),
    onUnauthorized: () => bus.emit(AuthEvent.logout),
  );
});

/// 全局 Dio 实例
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: kApiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      contentType: 'application/json',
      responseType: ResponseType.json,
    ),
  );

  // 拦截器链（按顺序）
  dio.interceptors.addAll([
    LogInterceptor(
      requestBody: true,
      responseBody: true,
      logPrint: (obj) => print('[HTTP] $obj'),
    ),
    ref.read(authInterceptorProvider),
  ]);

  return dio;
});
