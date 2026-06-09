// HomeMatch 基础 smoke test
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:homematch/app.dart';

void main() {
  testWidgets('HomeMatch app boots without error', (WidgetTester tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: HomeMatchApp(),
      ),
    );
    // 让框架渲染几帧
    await tester.pump();
    // 验证根 widget 渲染了
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
