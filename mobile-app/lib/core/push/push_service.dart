/// 推送服务（C6 引入）
///
/// 职责：
/// 1. 启动时 init Firebase（无 google-services.json 时静默失败）
/// 2. 监听 authEventBus：login 触发设备注册、logout 触发设备注销
/// 3. iOS 推送权限场景化请求（合作/邀请页进入时）
///
/// 设计要点：
/// - 所有 Firebase 调用包 try/catch — dev 环境无凭证时不阻塞登录
/// - 设备注册走 Dio，复用现有 JWT 拦截器
/// - fcm_token 存 FlutterSecureStorage（重启后能续用）
library;

import 'dart:async';
import 'dart:io' show Platform;

import 'package:device_info_plus/device_info_plus.dart' show DeviceInfoPlugin;
import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_event_bus.dart';
import '../network/api_exception.dart';
import '../network/dio_client.dart';

/// 推送服务（singleton）
class PushService {
  PushService(this._ref);
  final Ref _ref;

  bool _initialized = false;
  bool _firebaseAvailable = false;
  String? _cachedFcmToken;

  /// 在 main() 启动时调用一次
  Future<void> init() async {
    if (_initialized) return;
    _initialized = true;
    logger.i('PushService init start');

    // 1. 初始化 Firebase（无凭证时静默失败）
    _firebaseAvailable = await _tryInitFirebase();
    if (!_firebaseAvailable) {
      logger.w(
        'Firebase init failed - push will be no-op (dev mode or missing google-services.json)',
      );
    }

    // 2. 监听 auth 事件
    final bus = _ref.read(authEventBusProvider);
    bus.addListener(_onAuthEvent);
    _ref.onDispose(() => bus.removeListener(_onAuthEvent));

    // 3. 监听 FCM token 刷新
    if (_firebaseAvailable) {
      FirebaseMessaging.instance.onTokenRefresh.listen((newToken) {
        logger.i('FCM token refreshed');
        _cachedFcmToken = newToken;
        _persistToken(newToken);
        // token 变了：重新注册到后端
        _registerDevice(token: newToken).catchError((e) {
          logger.e('FCM token refresh register failed: $e');
          return -1;
        });
      });
    }

    logger.i('PushService init done (firebase=$_firebaseAvailable)');
  }

  Future<bool> _tryInitFirebase() async {
    try {
      // 默认配置（iOS 自动读 GoogleService-Info.plist，Android 自动读 google-services.json）
      await Firebase.initializeApp();
      return true;
    } catch (e) {
      logger.w('Firebase.initializeApp failed: $e');
      return false;
    }
  }

  void _onAuthEvent() {
    final bus = _ref.read(authEventBusProvider);
    final event = bus.lastEvent;
    if (event == null) return;

    if (event.forceLogout) {
      _unregisterDevice();
    } else {
      _registerOnLogin();
    }
  }

  /// 登录后：取 FCM token + 调后端注册
  Future<void> _registerOnLogin() async {
    if (!_firebaseAvailable) {
      logger.w('Skip device register: firebase not available');
      return;
    }
    try {
      // 场景化：iOS 需要先弹权限请求
      await _requestPermissionIfNeeded();

      final token = await FirebaseMessaging.instance.getToken();
      if (token == null) {
        logger.w('FCM getToken returned null');
        return;
      }
      _cachedFcmToken = token;
      await _persistToken(token);
      await _registerDevice(token: token);
      logger.i('Device registered (fcm_token=${token.substring(0, 20)}...)');
    } catch (e, st) {
      logger.e('Device register failed', error: e, stackTrace: st);
    }
  }

  /// 调后端 POST /v1/devices/register
  Future<int> _registerDevice({required String token}) async {
    final dio = _ref.read(dioProvider);
    final platform = Platform.isIOS ? 'ios' : Platform.isAndroid ? 'android' : 'unknown';
    final deviceModel = await _getDeviceModel();
    final osVersion = await _getOsVersion();

    try {
      final resp = await dio.post(
        '/v1/devices/register',
        data: {
          'fcm_token': token,
          'platform': platform,
          if (deviceModel != null) 'device_model': deviceModel,
          if (osVersion != null) 'os_version': osVersion,
        },
      );
      final apiResp = ApiResponse.fromJson(
        resp.data as Map<String, dynamic>,
        (data) => data as Map<String, dynamic>,
      );
      if (!apiResp.isOk) {
        throw ApiException(code: apiResp.code, message: apiResp.message);
      }
      return 0;
    } on DioException catch (e) {
      throw ApiException(
        code: -1,
        message: '网络错误: ${e.message}',
        httpStatus: e.response?.statusCode,
      );
    }
  }

  /// 登出时注销：调后端 DELETE /v1/devices/{token}
  Future<void> _unregisterDevice() async {
    final token = _cachedFcmToken ?? await _loadPersistedToken();
    if (token == null) {
      logger.w('No cached FCM token, skip unregister');
      return;
    }
    try {
      final dio = _ref.read(dioProvider);
      await dio.delete('/v1/devices/$token');
      logger.i('Device unregistered (fcm_token=${token.substring(0, 20)}...)');
    } catch (e) {
      logger.e('Device unregister failed: $e');
    } finally {
      _cachedFcmToken = null;
      await _deletePersistedToken();
    }
  }

  /// iOS 推送权限场景化请求（避免启动立即弹被 App Store 拒）
  /// - 已在合作/邀请页进入时由 router listener 调
  /// - Android 13+ 也需要 runtime 权限请求
  Future<bool> _requestPermissionIfNeeded() async {
    if (!_firebaseAvailable) return false;
    try {
      final settings = await FirebaseMessaging.instance.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );
      final granted = settings.authorizationStatus == AuthorizationStatus.authorized ||
          settings.authorizationStatus == AuthorizationStatus.provisional;
      logger.i('Push permission granted: $granted (status=${settings.authorizationStatus})');
      return granted;
    } catch (e) {
      logger.w('Request push permission failed: $e');
      return false;
    }
  }

  /// 公开方法：场景化请求权限（router listener 调用）
  Future<bool> requestPermissionIfNeeded() => _requestPermissionIfNeeded();

  // ===== 设备信息（注册时上报）=====

  Future<String?> _getDeviceModel() async {
    try {
      if (Platform.isIOS) {
        final info = await DeviceInfoPlugin().iosInfo;
        return info.utsname.machine; // e.g. "iPhone17,1"
      } else if (Platform.isAndroid) {
        final info = await DeviceInfoPlugin().androidInfo;
        return '${info.manufacturer} ${info.model}';
      }
    } catch (e) {
      logger.w('Get device model failed: $e');
    }
    return null;
  }

  Future<String?> _getOsVersion() async {
    try {
      if (Platform.isIOS) {
        final info = await DeviceInfoPlugin().iosInfo;
        return info.systemVersion; // e.g. "26.5"
      } else if (Platform.isAndroid) {
        final info = await DeviceInfoPlugin().androidInfo;
        return 'Android ${info.version.release} (SDK ${info.version.sdkInt})';
      }
    } catch (e) {
      logger.w('Get OS version failed: $e');
    }
    return null;
  }

  // ===== Token 持久化 =====

  Future<void> _persistToken(String token) async {
    try {
      final storage = _ref.read(secureStorageProvider);
      await storage.write(key: 'fcm_token', value: token);
    } catch (e) {
      logger.w('Persist FCM token failed: $e');
    }
  }

  Future<String?> _loadPersistedToken() async {
    try {
      final storage = _ref.read(secureStorageProvider);
      return await storage.read(key: 'fcm_token');
    } catch (e) {
      return null;
    }
  }

  Future<void> _deletePersistedToken() async {
    try {
      final storage = _ref.read(secureStorageProvider);
      await storage.delete(key: 'fcm_token');
    } catch (e) {
      logger.w('Delete persisted FCM token failed: $e');
    }
  }
}

/// Logger wrapper（避免直接依赖 logger 包导致循环 import）
class _Logger {
  void i(String msg) {
    if (kDebugMode) debugPrint('[PushService] $msg');
  }

  void w(String msg) {
    if (kDebugMode) debugPrint('[PushService][WARN] $msg');
  }

  void e(String msg, {Object? error, StackTrace? stackTrace}) {
    if (kDebugMode) {
      debugPrint('[PushService][ERROR] $msg${error != null ? " $error" : ""}');
      if (stackTrace != null) debugPrint(stackTrace.toString());
    }
  }
}

final logger = _Logger();

/// Riverpod provider
final pushServiceProvider = Provider<PushService>((ref) {
  return PushService(ref);
});
