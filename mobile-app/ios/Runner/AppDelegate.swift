import Flutter
import UIKit
import UserNotifications

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    // C4: 注册 UNUserNotificationCenter delegate（flutter_local_notifications 必需）
    if #available(iOS 10.0, *) {
      UNUserNotificationCenter.current().delegate = self
    }
    // C4: 注册 APNs 远程通知（FCM 会用此 deviceToken）
    application.registerForRemoteNotifications()
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
  }

  // C4: APNs 注册成功回调 → 传给 firebase_messaging
  override func application(
    _ application: UIApplication,
    didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
  ) {
    // firebase_messaging plugin 内部会监听此回调
    super.application(application, didRegisterForRemoteNotificationsWithDeviceToken: deviceToken)
  }

  // C4: APNs 注册失败回调
  override func application(
    _ application: UIApplication,
    didFailToRegisterForRemoteNotificationsWithError error: Error
  ) {
    super.application(application, didFailToRegisterForRemoteNotificationsWithError: error)
  }
}
