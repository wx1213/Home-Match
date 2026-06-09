/// 认证服务 - 登录/登出

library;
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/dio_client.dart';
import '../../core/network/api_exception.dart';
import 'auth_state.dart';

class AuthService {
  AuthService(this._dio);
  final Dio _dio;

  /// 微信登录（mock 模式：传入 code，自动用 mock openid 注册/登录）
  Future<AuthState> loginWithWechat(String code) async {
    try {
      final resp = await _dio.post(
        '/v1/auth/wechat-login',
        data: {'code': code},
      );
      final apiResp = ApiResponse.fromJson(
        resp.data as Map<String, dynamic>,
        (data) => data as Map<String, dynamic>,
      );
      if (!apiResp.isOk) {
        throw ApiException(
          code: apiResp.code,
          message: apiResp.message,
        );
      }
      final data = apiResp.data!;
      final user = data['user'] as Map<String, dynamic>;
      return AuthState(
        isLoggedIn: true,
        userId: user['id'] as int,
        userName: user['name'] as String,
        displayName: user['display_name'] as String?,
        avatarUrl: user['avatar_url'] as String?,
        creditScore: (user['credit_score'] as num?)?.toDouble(),
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String,
      );
    } on DioException catch (e) {
      throw ApiException(
        code: -1,
        message: '网络错误: ${e.message}',
        httpStatus: e.response?.statusCode,
      );
    }
  }
}

final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(ref.read(dioProvider));
});
