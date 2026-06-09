/// HTTP 客户端 - dio + 拦截器链

library;
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../auth/auth_event_bus.dart';
import 'auth_interceptor.dart';

/// API base URL
/// iOS 模拟器/Android 模拟器访问宿主 localhost 都用这个
const String kApiBaseUrl = 'http://localhost:8000';

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
