/// Dio 拦截器 - 安全的 HTTP 日志（[Sprint1-P0] 生产脱敏）
///
/// 与 dio 自带 LogInterceptor 的区别：
/// 1. 生产环境（``AppEnv.isProduction``）**完全不打印** request/response body
///    （即使开发者忘了关 debug 日志，body 也已经被这里二次过滤）
/// 2. 始终对**敏感字段**做脱敏：token / access_token / refresh_token /
///    password / phone / openid / unionid / id_card / sms_code / apple_user_id
/// 3. 只打印 method/path/status/latency，不打印完整 query（避免 ?token=xxx 泄漏）
///
/// ## 风险与权衡
///
/// - dio LogInterceptor 会打 print()，iOS Xcode / Android logcat 都能直接 grep
/// - 真实泄漏路径：用户用 adb / Xcode 抓 log → 上传后端日志到 Sentry
///   → Sentry 后台能搜到 token（如果 body 没脱敏）
/// - 本拦截器在源头解决问题，body 不进 print 就不进任何日志通道
library;

import 'dart:convert';

import 'package:dio/dio.dart';

import '../env/app_env.dart';

/// 敏感字段名单（key 命中即整 value 替换为 ``***``）
const Set<String> _sensitiveKeys = {
  'token',
  'access_token',
  'refresh_token',
  'authorization',
  'password',
  'phone',
  'phone_encrypted',
  'phone_hash',
  'openid',
  'unionid',
  'apple_user_id',
  'id_card',
  'sms_code',
  'id_token',
  'identity_token',
  'wechat_unionid',
  'wechat_openid',
  'credit_card',
  'cvv',
  'pin',
};

/// 脱敏单个 value
String _maskValue(dynamic value) {
  if (value == null) return 'null';
  if (value is String && value.isEmpty) return '""';
  return '***';
}

/// 递归脱敏 Map/List
dynamic _sanitize(dynamic obj) {
  if (obj is Map) {
    return obj.map((k, v) {
      if (k is String && _sensitiveKeys.contains(k.toLowerCase())) {
        return MapEntry(k, _maskValue(v));
      }
      return MapEntry(k, _sanitize(v));
    });
  }
  if (obj is List) {
    return obj.map(_sanitize).toList();
  }
  return obj;
}

/// [Sprint3 修复] 检测 body 是否含不能 JSON 序列化的对象（multipart）。
///  返回 true 表示**完全不打 body**（避免触发 DioEncoder 抛错）。
bool _containsNonEncodable(dynamic obj) {
  if (obj is FormData) return true;
  if (obj is List) {
    for (final x in obj) {
      if (_containsNonEncodable(x)) return true;
    }
  }
  if (obj is Map) {
    for (final v in obj.values) {
      if (_containsNonEncodable(v)) return true;
    }
  }
  return false;
}

/// 把 dio 的 RequestOptions/Response 对象转成可安全打印的字符串
/// （public 让单测能直接调用验证脱敏）
String formatLogLine({
  required String method,
  required String path,
  int? status,
  int? latencyMs,
  Object? body,
  String? error,
}) {
  final buf = StringBuffer();
  buf.write('[$method $path');
  if (status != null) {
    buf.write(' → $status');
  }
  if (latencyMs != null) {
    buf.write(' (${latencyMs}ms)');
  }
  buf.write(']');

  if (error != null) {
    buf.write('\n  ERR: $error');
  }

  // body 只在 dev/staging 打，且**先脱敏**
  // 注意：dio v5 的 FormData / MultipartFile 不能被 JsonEncoder 序列化
  //       如果 try 转换时抛错，会导致整个请求失败（[Sprint3 修复]）
  if (body != null && !AppEnv.isProduction) {
    // FormData / Map 包含 FormData / 其它不能 JSON 序列化的对象
    // → 只打 method+path，不打 body
    final shouldSkipBody = _containsNonEncodable(body);
    if (!shouldSkipBody) {
      try {
        final sanitized = _sanitize(body);
        final encoded = const JsonEncoder.withIndent('  ').convert(sanitized);
        buf.write('\n  BODY: $encoded');
      } catch (e) {
        // 兜底：序列化失败不影响请求主流程
        buf.write('\n  BODY: <${body.runtimeType} not serializable>');
      }
    } else {
      buf.write('\n  BODY: <multipart — omitted>');
    }
  }

  return buf.toString();
}

/// 替代 dio 内置 LogInterceptor 的安全版本
///
/// 用法：
/// ```dart
/// dio.interceptors.add(SafeLogInterceptor());
/// ```
class SafeLogInterceptor extends Interceptor {
  /// 早于 onRequest 记录时间戳，onResponse/onError 算 latency
  final Map<int, DateTime> _starts = {};

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    _starts[options.hashCode] = DateTime.now();

    if (AppEnv.isProduction) {
      // 生产：只打 method + path（query 里可能有 token）
      //   path 已经是 baseUrl 之后的相对路径，不含 query
      //   如果你看到 query 在这里，请检查 dio 是否被 misuse
      debugPrint(formatLogLine(
        method: options.method,
        path: options.path,
        body: null, // 强制 null → 生产不打 body
      ));
    } else {
      // dev/staging：打 method + path + body（脱敏后）
      debugPrint(formatLogLine(
        method: options.method,
        path: options.path,
        body: options.data,
      ));
    }
    handler.next(options);
  }

  @override
  void onResponse(
    Response<dynamic> response,
    ResponseInterceptorHandler handler,
  ) {
    final start = _starts.remove(response.requestOptions.hashCode);
    final latencyMs = start == null
        ? null
        : DateTime.now().difference(start).inMilliseconds;

    debugPrint(formatLogLine(
      method: response.requestOptions.method,
      path: response.requestOptions.path,
      status: response.statusCode,
      latencyMs: latencyMs,
      body: response.data,
    ));
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    final start = _starts.remove(err.requestOptions.hashCode);
    final latencyMs = start == null
        ? null
        : DateTime.now().difference(start).inMilliseconds;

    // [Sprint3 调试] 打印完整异常类型 + 堆栈，方便诊断上传等 multipart 请求失败
    debugPrint(formatLogLine(
      method: err.requestOptions.method,
      path: err.requestOptions.path,
      status: err.response?.statusCode,
      latencyMs: latencyMs,
      body: err.response?.data,
      error: err.message,
    ));
    debugPrint('  [DioError type=${err.type}] ${err.error}');
    if (err.stackTrace != null) {
      debugPrint('  [StackTrace] ${err.stackTrace.toString().split('\n').take(8).join('\n')}');
    }
    handler.next(err);
  }
}

/// ``debugPrint`` 是 flutter foundation 的；直接调 print() 也行
/// 这里用 debugPrint 避免在 release 构建里 print 仍然输出
void debugPrint(String msg) {
  // 生产模式下完全不打
  // （即使 dio 触发 onError 也不会泄漏）
  if (AppEnv.isProduction && !kDebugModeBody) return;
  // ignore: avoid_print
  print(msg);
}

/// ``kDebugModeBody`` 单独开关 — 测试用 force-on
const bool kDebugModeBody = bool.fromEnvironment(
  'DEBUG_BODY_LOG',
  defaultValue: false,
);
