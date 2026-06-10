// P1-0 验证：DevIdentity 数据类 + tile 渲染（_DevUserTile 是 private，这里只验证数据 + 通用 ListTile 渲染）
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:homematch/features/profile/profile_screen.dart' show DevIdentity;

void main() {
  group('DevIdentity (P1-0 验证)', () {
    test('fromJson 正确解析后端响应', () {
      final json = {
        'code': 'dev_alice',
        'user_id': 18,
        'display_name': '邓嘉怡',
        'name': '邓嘉怡',
        'credit_score': 85.0,
        'is_verified': true,
        'role': 'buyer',
        'role_label': '买方代表',
        'demand_count': 2,
        'property_count': 0,
      };
      final id = DevIdentity.fromJson(json);
      expect(id.code, 'dev_alice');
      expect(id.userId, 18);
      expect(id.displayName, '邓嘉怡');
      expect(id.creditScore, 85.0);
      expect(id.isVerified, true);
      expect(id.role, 'buyer');
      expect(id.roleLabel, '买方代表');
      expect(id.demandCount, 2);
      expect(id.propertyCount, 0);
    });

    testWidgets('通用 ListTile + #userId 徽章渲染正确', (WidgetTester tester) async {
      // 这模拟 _DevUserTile 的关键 UI：标题行有 #userId 徽章 + display_name
      const id = DevIdentity(
        code: 'dev_alice',
        userId: 18,
        displayName: '邓嘉怡',
        name: '邓嘉怡',
        creditScore: 85.0,
        isVerified: true,
        role: 'buyer',
        roleLabel: '买方代表',
        demandCount: 2,
        propertyCount: 0,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ListTile(
              title: Row(
                children: [
                  // #userId 徽章（P1-0 关键：显眼显示）
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.amber.shade100,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text('#${id.userId}'),
                  ),
                  const SizedBox(width: 8),
                  Text(id.displayName ?? '用户'),
                ],
              ),
              subtitle: Text('${id.roleLabel} · 信用 ${id.creditScore.toStringAsFixed(1)}'),
            ),
          ),
        ),
      );

      // 验证关键 UI 元素存在
      expect(find.text('#18'), findsOneWidget);
      expect(find.text('邓嘉怡'), findsOneWidget);
      expect(find.text('买方代表 · 信用 85.0'), findsOneWidget);
    });
  });
}
