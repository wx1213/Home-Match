/// 鉴权拦截器 - 自动注入 JWT + 处理 401

library;
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../auth/auth_event_bus.dart';

class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._storage, {this.onUnauthorized});

  final FlutterSecureStorage _storage;
  final void Function()? onUnauthorized;
  static const _tokenKey = 'access_token';
  static const _refreshKey = 'refresh_token';

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _storage.read(key: _tokenKey);
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    // 401 时清理 token 并触发强制登出事件
    if (err.response?.statusCode == 401) {
      await _storage.delete(key: _tokenKey);
      await _storage.delete(key: _refreshKey);
      onUnauthorized?.call();
    }
    handler.next(err);
  }
}
