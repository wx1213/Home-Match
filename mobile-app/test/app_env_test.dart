// P2-1 验证：AppEnv 默认值与 --dart-define 注入
import 'package:flutter_test/flutter_test.dart';

import 'package:homematch/core/env/app_env.dart';

void main() {
  group('AppEnv (P2-1)', () {
    test('默认值：dev 模式 + localhost:8000', () {
      // 不传 --dart-define 时用默认
      expect(AppEnv.apiBaseUrl, 'http://localhost:8000');
      expect(AppEnv.envName, 'development');
      expect(AppEnv.isProduction, false);
      expect(AppEnv.enableDevLogin, true);
    });

    test('summary 包含 DEV 标记（dev 模式）', () {
      expect(AppEnv.summary, contains('[DEV]'));
      expect(AppEnv.summary, contains('development'));
    });
  });
}
