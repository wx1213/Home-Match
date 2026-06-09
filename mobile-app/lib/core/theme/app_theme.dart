/// HomeMatch 主题 - Material 3
library;

import 'package:flutter/material.dart';

import 'app_tokens.dart';

class AppTheme {
  // 主品牌色
  static const Color _primaryLight = Color(0xFF1976D2);
  static const Color _primaryDark = Color(0xFF90CAF9);

  /// 浅色主题
  static ThemeData get light => _buildTheme(
        brightness: Brightness.light,
        primary: _primaryLight,
        onPrimary: Colors.white,
        surface: const Color(0xFFFAFAFA),
        onSurface: const Color(0xFF1C1B1F),
      );

  /// 深色主题
  static ThemeData get dark => _buildTheme(
        brightness: Brightness.dark,
        primary: _primaryDark,
        onPrimary: const Color(0xFF003C8F),
        surface: const Color(0xFF121212),
        onSurface: const Color(0xFFE6E1E5),
      );

  static ThemeData _buildTheme({
    required Brightness brightness,
    required Color primary,
    required Color onPrimary,
    required Color surface,
    required Color onSurface,
  }) {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: primary,
      brightness: brightness,
    ).copyWith(
      surface: surface,
      onSurface: onSurface,
    );

    final isLight = brightness == Brightness.light;
    final cardColor = isLight ? Colors.white : const Color(0xFF1E1E1E);
    final dividerColor = onSurface.withValues(alpha: 0.08);

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      brightness: brightness,
      scaffoldBackgroundColor: surface,
      splashFactory: InkSparkle.splashFactory,
      appBarTheme: AppBarTheme(
        backgroundColor: surface,
        foregroundColor: onSurface,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: onSurface,
          fontSize: 18,
          fontWeight: FontWeight.w600,
        ),
      ),
      cardTheme: CardThemeData(
        color: cardColor,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(HMRadius.lg),
          side: BorderSide(color: dividerColor, width: 0.5),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: dividerColor,
        space: 1,
        thickness: 0.5,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(HMRadius.md),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(HMRadius.md),
          ),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          minimumSize: const Size(0, 36),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(HMRadius.sm),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(HMRadius.md),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(HMRadius.md),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(HMRadius.md),
          borderSide: BorderSide(color: colorScheme.primary, width: 1.5),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      chipTheme: ChipThemeData(
        side: BorderSide.none,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(HMRadius.sm),
        ),
        labelStyle: TextStyle(fontSize: 13, color: onSurface),
        secondaryLabelStyle: TextStyle(fontSize: 13, color: onPrimary),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 64,
        backgroundColor: cardColor,
        indicatorColor: colorScheme.primaryContainer,
        elevation: 0,
        labelTextStyle: WidgetStatePropertyAll(
          TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w500,
            color: onSurface,
          ),
        ),
      ),
      tabBarTheme: TabBarThemeData(
        labelColor: colorScheme.primary,
        unselectedLabelColor: onSurface.withValues(alpha: 0.6),
        indicatorSize: TabBarIndicatorSize.label,
        indicator: UnderlineTabIndicator(
          borderSide: BorderSide(color: colorScheme.primary, width: 2.5),
          insets: const EdgeInsets.symmetric(horizontal: 24),
        ),
        labelStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w400),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: colorScheme.primary,
        foregroundColor: onPrimary,
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(HMRadius.lg),
        ),
        extendedTextStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
      textTheme: TextTheme(
        displayLarge: TextStyle(color: onSurface, fontSize: 32, fontWeight: FontWeight.w700, height: 1.2),
        displayMedium: TextStyle(color: onSurface, fontSize: 28, fontWeight: FontWeight.w700, height: 1.25),
        headlineLarge: TextStyle(color: onSurface, fontSize: 24, fontWeight: FontWeight.w600, height: 1.3),
        headlineMedium: TextStyle(color: onSurface, fontSize: 20, fontWeight: FontWeight.w600, height: 1.3),
        titleLarge: TextStyle(color: onSurface, fontSize: 18, fontWeight: FontWeight.w600, height: 1.3),
        titleMedium: TextStyle(color: onSurface, fontSize: 16, fontWeight: FontWeight.w500, height: 1.3),
        titleSmall: TextStyle(color: onSurface, fontSize: 14, fontWeight: FontWeight.w500, height: 1.3),
        bodyLarge: TextStyle(color: onSurface, fontSize: 16, fontWeight: FontWeight.w400, height: 1.5),
        bodyMedium: TextStyle(color: onSurface, fontSize: 14, fontWeight: FontWeight.w400, height: 1.45),
        bodySmall: TextStyle(color: onSurface.withValues(alpha: 0.7), fontSize: 12, height: 1.4),
        labelLarge: TextStyle(color: onSurface, fontSize: 14, fontWeight: FontWeight.w600, height: 1.2),
        labelMedium: TextStyle(color: onSurface, fontSize: 12, fontWeight: FontWeight.w500, height: 1.2),
        labelSmall: TextStyle(color: onSurface.withValues(alpha: 0.6), fontSize: 10, height: 1.2),
      ),
    );
  }
}
