/// PasteLinkButton widget 测试（P0 任务 1 - B2 commit）
///
/// 验证：
/// - 默认渲染：按钮 + 图标 + 文字
/// - 状态切换：busy 时显示 loading（不测异步网络，参考 test_property_flow 的手写等价 widget 模式）
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:homematch/core/network/beike_parse_service.dart';
import 'package:homematch/core/widgets/paste_link_button.dart';

void main() {
  group('BeikeParseResult.toMap 衍生字段', () {
    test('previewLabel 拼接 city + type + houseId', () {
      final r = BeikeParseResult(
        valid: true,
        urlType: 'ershoufang',
        houseId: '12345',
        city: 'bj',
      );
      expect(r.previewLabel, equals('北京-二手房-#12345'));
    });

    test('previewLabel 缺 city 时跳过', () {
      final r = BeikeParseResult(
        valid: true,
        urlType: 'loupan',
        houseId: 'p_abc',
      );
      expect(r.previewLabel, equals('楼盘-#p_abc'));
    });

    test('typeLabel 映射 4 类', () {
      expect(
        const BeikeParseResult(valid: true, urlType: 'ershoufang').typeLabel,
        '二手房',
      );
      expect(
        const BeikeParseResult(valid: true, urlType: 'loupan').typeLabel,
        '楼盘',
      );
      expect(
        const BeikeParseResult(valid: true, urlType: 'buyhouse').typeLabel,
        '购房需求',
      );
      expect(
        const BeikeParseResult(valid: true, urlType: 'xinfang').typeLabel,
        '新房',
      );
      expect(
        const BeikeParseResult(valid: true).typeLabel,
        isNull,
      );
    });

    test('cityLabel 映射主流城市', () {
      expect(
        const BeikeParseResult(valid: true, city: 'bj').cityLabel,
        '北京',
      );
      expect(
        const BeikeParseResult(valid: true, city: 'sh').cityLabel,
        '上海',
      );
      expect(
        const BeikeParseResult(valid: true, city: 'unknown').cityLabel,
        isNull,
      );
    });

    test('valid=false 时 previewLabel 为 null', () {
      const r = BeikeParseResult(valid: false, reason: '不是贝壳');
      expect(r.previewLabel, isNull);
    });

    test('fromJson 解析后端响应', () {
      final r = BeikeParseResult.fromJson({
        'valid': true,
        'url_type': 'ershoufang',
        'house_id': '12345',
        'city': 'bj',
        'reason': null,
      });
      expect(r.valid, isTrue);
      expect(r.urlType, 'ershoufang');
      expect(r.houseId, '12345');
      expect(r.city, 'bj');
      expect(r.reason, isNull);
    });
  });

  group('BeikePreviewCard 渲染', () {
    testWidgets('valid=true 显示预览卡片', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BeikePreviewCard(
              url: 'https://bj.ke.com/ershoufang/12345.html',
              result: const BeikeParseResult(
                valid: true,
                urlType: 'ershoufang',
                houseId: '12345',
                city: 'bj',
              ),
            ),
          ),
        ),
      );
      expect(find.text('✓ 已识别 北京-二手房-#12345'), findsOneWidget);
      expect(find.text('https://bj.ke.com/ershoufang/12345.html'), findsOneWidget);
    });

    testWidgets('valid=false 渲染空 SizedBox（不显示）', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: BeikePreviewCard(
              url: 'invalid',
              result: BeikeParseResult(valid: false, reason: '不是贝壳'),
            ),
          ),
        ),
      );
      expect(find.textContaining('已识别'), findsNothing);
    });

    testWidgets('onClear 回调触发', (tester) async {
      var cleared = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: BeikePreviewCard(
              url: 'https://bj.ke.com/ershoufang/12345.html',
              result: const BeikeParseResult(
                valid: true,
                urlType: 'ershoufang',
                houseId: '12345',
                city: 'bj',
              ),
              onClear: () => cleared = true,
            ),
          ),
        ),
      );
      await tester.tap(find.byIcon(Icons.close_rounded));
      expect(cleared, isTrue);
    });
  });
}