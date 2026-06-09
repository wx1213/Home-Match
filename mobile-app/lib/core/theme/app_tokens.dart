/// HomeMatch 设计 Tokens - 颜色 / 间距 / 圆角 / 阴影
library;

import 'package:flutter/material.dart';

/// 间距（8pt 网格）
class HMSpace {
  static const double xxs = 4;
  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 48;
}

/// 圆角
class HMRadius {
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double full = 9999;
}

/// 业务色（与文档 [docs/04-ui-ux-guidelines.md] §2.1 对齐）
class HMColors {
  // 信用分颜色
  static const Color creditGold = Color(0xFFFFD700);
  static const Color creditGreen = Color(0xFF2E7D32);
  static const Color creditBlue = Color(0xFF1976D2);
  static const Color creditOrange = Color(0xFFF57C00);
  static const Color creditRed = Color(0xFFC62828);

  // 状态色
  static const Color success = Color(0xFF2E7D32);
  static const Color warning = Color(0xFFF57C00);
  static const Color error = Color(0xFFC62828);
  static const Color info = Color(0xFF1976D2);

  // 邀请状态色
  static const Color statusPending = Color(0xFFF57C00);
  static const Color statusAccepted = Color(0xFF1976D2);
  static const Color statusProposal = Color(0xFF7B1FA2);
  static const Color statusHandshaked = Color(0xFF2E7D32);
  static const Color statusRejected = Color(0xFFC62828);
  static const Color statusExpired = Color(0xFF757575);

  // 渐变
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [Color(0xFF1976D2), Color(0xFF1565C0)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient warmGradient = LinearGradient(
    colors: [Color(0xFFFFA726), Color(0xFFFB8C00)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

/// 阴影（Z 轴层次）
class HMShadow {
  static List<BoxShadow> level1 = [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.06),
      blurRadius: 8,
      offset: const Offset(0, 2),
    ),
  ];

  static List<BoxShadow> level2 = [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.08),
      blurRadius: 16,
      offset: const Offset(0, 4),
    ),
  ];

  static List<BoxShadow> level3 = [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.12),
      blurRadius: 24,
      offset: const Offset(0, 8),
    ),
  ];
}
