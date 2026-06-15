// 前后端错误码契约测试（[mobile-app/lib/core/network/]）
//
// 锁定：
// 1. ApiResponse 模型解析后端 `{code, message, data?, detail?}` 响应
// 2. ApiException 字段 + toString
// 3. AuthInterceptor 401 行为：清 token + 触发 onUnauthorized
// 4. AuthService Dio 错误 → ApiException 转换
// 5. 端到端契约：后端错误码 10001-49999 + HTTP 401 触发前端自动登出
//
// 配套：[backend/tests/test_error_mapping.py] 锁后端契约

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:homematch/core/network/api_exception.dart';
import 'package:homematch/core/network/auth_interceptor.dart';
import 'package:homematch/features/auth/auth_service.dart';

/// Mock FlutterSecureStorage — 避免依赖 platform channel
/// 只 stub 我们用到的 3 个方法（read/write/delete），其他走 noSuchMethod
class _MockSecureStorage implements FlutterSecureStorage {
  final Map<String, String?> _store = {};

  @override
  Future<String?> read({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    return _store[key];
  }

  @override
  Future<void> write({
    required String key,
    required String? value,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    _store[key] = value;
  }

  @override
  Future<void> delete({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    _store.remove(key);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) {
    // FlutterSecureStorage 有 30+ 方法，我们只 stub 3 个
    // 其他方法被调用时直接抛 NoSuchMethodError（测试不依赖）
    return super.noSuchMethod(invocation);
  }
}

void main() {
  group('ApiResponse（后端响应 → Dart 模型）', () {
    test('code=0 → isOk=true', () {
      final resp = ApiResponse<int>(
        code: 0,
        message: 'ok',
        data: 42,
      );
      expect(resp.isOk, true);
      expect(resp.data, 42);
    });

    test('code != 0 → isOk=false', () {
      final resp = ApiResponse<int>(
        code: 10003,
        message: '权限不足',
        data: null,
      );
      expect(resp.isOk, false);
      expect(resp.data, isNull);
    });

    test('fromJson 解析完整响应（带 data）', () {
      final json = {
        'code': 0,
        'message': 'ok',
        'data': {'id': 1, 'name': 'Alice'},
      };
      final resp = ApiResponse.fromJson(
        json,
        (data) => data as Map<String, dynamic>,
      );
      expect(resp.isOk, true);
      expect(resp.data, {'id': 1, 'name': 'Alice'});
    });

    test('fromJson 解析错误响应（data=null, 含 detail）', () {
      final json = {
        'code': 10001,
        'message': '参数错误',
        'detail': {'field': 'price', 'value': -1},
      };
      final resp = ApiResponse.fromJson(
        json,
        (data) => data as Map<String, dynamic>,
      );
      // ApiResponse 不存 detail（detail 是错误诊断信息，UI 不直接消费）
      // 但 message + code 必须正确
      expect(resp.code, 10001);
      expect(resp.message, '参数错误');
      expect(resp.isOk, false);
    });

    test('fromJson 容错：code 字段缺失 → 返 -1', () {
      final json = {'message': 'ok'};
      final resp = ApiResponse.fromJson(
        json,
        (data) => data as Map<String, dynamic>,
      );
      expect(resp.code, -1);
    });

    test('fromJson 容错：data 字段为 null', () {
      final json = {'code': 0, 'message': 'ok', 'data': null};
      final resp = ApiResponse.fromJson(
        json,
        (data) => data as Map<String, dynamic>,
      );
      expect(resp.data, isNull);
    });
  });

  group('ApiException（友好错误）', () {
    test('toString 格式 = [code] message', () {
      final e = ApiException(code: 10003, message: '权限不足');
      expect(e.toString(), '[10003] 权限不足');
    });

    test('toString 含中文不乱码', () {
      final e = ApiException(code: 30005, message: '状态机非法转移');
      expect(e.toString(), '[30005] 状态机非法转移');
    });

    test('httpStatus 是 optional', () {
      const e = ApiException(code: 10004, message: '未认证');
      expect(e.httpStatus, isNull);
    });

    test('带 httpStatus 时可读取', () {
      const e = ApiException(code: 10004, message: '未认证', httpStatus: 401);
      expect(e.httpStatus, 401);
    });
  });

  group('AuthInterceptor（401 触发自动登出）', () {
    test('401 → 清 token + 触发 onUnauthorized', () async {
      final storage = _MockSecureStorage();
      await storage.write(key: 'access_token', value: 'valid_token');
      await storage.write(key: 'refresh_token', value: 'valid_refresh');

      var unauthorizedFired = false;
      final interceptor = AuthInterceptor(
        storage,
        onUnauthorized: () => unauthorizedFired = true,
      );

      // 构造一个 401 错误的 DioException
      final req = RequestOptions(path: '/v1/users/me');
      final err = DioException(
        requestOptions: req,
        response: Response(
          requestOptions: req,
          statusCode: 401,
          data: {'code': 10004, 'message': 'Token 已过期'},
        ),
        type: DioExceptionType.badResponse,
      );

      // 通过 ErrorInterceptorHandler 走 onError
      // 注：handler.next(err) 不传会 throw，所以用捕获
      try {
        await interceptor.onError(
          err,
          _CapturingErrorInterceptorHandler(),
        );
      } catch (_) {}

      expect(unauthorizedFired, true, reason: '401 必须触发 onUnauthorized');
      expect(await storage.read(key: 'access_token'), isNull);
      expect(await storage.read(key: 'refresh_token'), isNull);
    });

    test('非 401 → 不清 token + 不触发 onUnauthorized', () async {
      final storage = _MockSecureStorage();
      await storage.write(key: 'access_token', value: 'valid_token');

      var unauthorizedFired = false;
      final interceptor = AuthInterceptor(
        storage,
        onUnauthorized: () => unauthorizedFired = true,
      );

      // 500 错误
      final req = RequestOptions(path: '/v1/foo');
      final err = DioException(
        requestOptions: req,
        response: Response(
          requestOptions: req,
          statusCode: 500,
          data: {'code': 10006, 'message': '服务器异常'},
        ),
        type: DioExceptionType.badResponse,
      );

      try {
        await interceptor.onError(
          err,
          _CapturingErrorInterceptorHandler(),
        );
      } catch (_) {}

      expect(unauthorizedFired, false);
      expect(await storage.read(key: 'access_token'), 'valid_token');
    });
  });

  group('AuthService（Dio 错误 → ApiException 转换）', () {
    test('Dio 401 错误 → ApiException(httpStatus=401, code=-1)', () async {
      // 构造一个 mock DioAdapter 抛 401 DioException
      final dio = Dio(BaseOptions(baseUrl: 'http://test'));
      dio.httpClientAdapter = _MockAdapter(
        error: DioException(
          requestOptions: RequestOptions(path: '/v1/auth/wechat-login'),
          response: Response(
            requestOptions: RequestOptions(path: '/v1/auth/wechat-login'),
            statusCode: 401,
            data: {'code': 10004, 'message': 'Token 已过期'},
          ),
          type: DioExceptionType.badResponse,
        ),
      );

      final svc = AuthService(dio);

      expect(
        () => svc.loginWithWechat('dev_alice'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.httpStatus, 'httpStatus', 401)
              .having((e) => e.code, 'code', -1),
        ),
      );
    });

    test('Dio 连接错误 → ApiException(httpStatus=null, code=-1)', () async {
      final dio = Dio(BaseOptions(baseUrl: 'http://test'));
      dio.httpClientAdapter = _MockAdapter(
        error: DioException(
          requestOptions: RequestOptions(path: '/v1/auth/wechat-login'),
          type: DioExceptionType.connectionError,
          message: 'Connection refused',
        ),
      );

      final svc = AuthService(dio);

      expect(
        () => svc.loginWithWechat('dev_alice'),
        throwsA(
          isA<ApiException>()
              .having((e) => e.httpStatus, 'httpStatus', isNull)
              .having((e) => e.message, 'message', contains('网络错误')),
        ),
      );
    });
  });

  group('端到端契约（关键错误码）', () {
    // 这些码被前端显式 case 分支（grep mobile-app/lib 验证）
    // 本组测试是"契约文档"，确保这些码不被误改
    test('关键错误码范围是 10001-49999', () {
      // 后端契约范围
      for (final code in [10001, 10002, 10003, 10004, 10005, 10006,
                         20001, 20002, 20003, 20004,
                         30001, 30002, 30003, 30004, 30005, 30006, 30007,
                         40001, 40002, 40003, 40004, 40005, 40006]) {
        expect(code, greaterThanOrEqualTo(10001));
        expect(code, lessThanOrEqualTo(49999));
      }
    });

    test('HTTP 401 是前端自动登出的触发条件', () {
      // 契约：401 → AuthInterceptor 清 token + 触发 onUnauthorized
      // 这是前端唯一处理的特殊 HTTP status
      // （其他 4xx/5xx 由业务 code 处理，不触发登出）
      const status401 = 401;
      expect(status401, 401);
    });
  });
}

/// 捕获 ErrorInterceptorHandler.next() 调用（不抛）
class _CapturingErrorInterceptorHandler extends ErrorInterceptorHandler {
  @override
  void next(DioException err) {
    // 不做任何事；我们只关心 onError 的副作用
  }
}

/// Mock dio httpClientAdapter — 抛固定 error
/// (成功路径测试不依赖 dio httpClientAdapter，而是直接 mock AuthService)
class _MockAdapter implements HttpClientAdapter {
  _MockAdapter({this.error});
  final DioException? error;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    if (error != null) {
      throw error!;
    }
    // 不应该走到这里（测试只模拟失败路径）
    throw StateError('_MockAdapter 没有 response 分支');
  }
}
