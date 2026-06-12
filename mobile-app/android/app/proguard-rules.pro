# Flutter / Dart
# Keep Dart VM symbols for stack traces; do not strip line numbers
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Keep generic signatures for reflection used by Dart's generic type checks
-keepattributes Signature
-keepattributes *Annotation*
-keepattributes EnclosingMethod
-keepattributes InnerClasses

# Riverpod (代码生成 + runtime reflection)
-keep class * extends com.google.inject.AbstractModule
-keep class * extends androidx.lifecycle.ViewModel { *; }
-keepclassmembers class * extends androidx.lifecycle.ViewModel {
    <init>(...);
}

# Dio (HTTP client — uses reflection in interceptor chains)
-keep class com.diolnx.** { *; }
-dontwarn com.diolnx.**

# firebase_messaging + firebase_core
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# image_picker + flutter_image_compress
-keep class com.imagepicker.** { *; }
-dontwarn com.imagepicker.**

# Hive (本地存储)
-keep class io.flutter.plugins.hive.** { *; }
-keep class * implements io.flutter.plugins.hive.** { *; }

# Kotlin
-keep class kotlin.Metadata { *; }
-keep class kotlin.coroutines.Continuation
-keepclassmembers class **$WhenMappings { <fields>; }

# 关闭 build 时混淆日志里大量 noise（flutter build apk --release 输出会更干净）
-dontnote **
