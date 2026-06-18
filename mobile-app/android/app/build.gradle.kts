import java.io.FileInputStream
import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
    // C5: Firebase 插件（google-services.json 由插件读取）
    id("com.google.gms.google-services")
}

// ============================================================
//  Release 签名配置（[Sprint1-P0] Android 上架硬阻断）
// ============================================================
//
//  为什么不直接 hardcode keystore path？
//  - keystore 文件和密码不能入 git
//  - CI 必须从 secret 注入（不同环境不同 key）
//
// 流程：
//  1. 拷贝 android/key.properties.example → android/key.properties（.gitignore 已忽略）
//  2. 填 4 个字段（storeFile / storePassword / keyAlias / keyPassword）
//  3. assembleRelease 走 signingConfigs.release（不再 fallback 到 debug）
//
// 如果 key.properties 缺失，signingConfigs.release 是空 config，
// Android Gradle Plugin 会在 assembleRelease 阶段自动报错：
//   "Keystore file not set for signing config release"
//   → 不会再出现"误用 debug 签名上架"的事故
//
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    namespace = "cn.hmatch.homematch"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "cn.hmatch.homematch"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    // === Release 签名 ===
    //   key.properties 存在时：读 4 字段配置 release keystore
    //   不存在时：空 config → release build 会 hard fail（不再误用 debug）
    signingConfigs {
        create("release") {
            if (keystorePropertiesFile.exists()) {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
            }
        }
    }

    buildTypes {
        release {
            // 改用 release signing config（之前误用 debug → 商店拒绝）
            signingConfig = signingConfigs.getByName("release")
            // 启用代码压缩 + 资源压缩（Play Store 上架体积更小 + 难逆向）
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
