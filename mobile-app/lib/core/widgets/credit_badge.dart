/// 信用分徽章
library;

import 'package:flutter/material.dart';

import '../theme/app_tokens.dart';

class CreditBadge extends StatelessWidget {
  final double score;
  final double size;
  final bool showLabel;
  final bool compact;

  const CreditBadge({
    super.key,
    required this.score,
    this.size = 36,
    this.showLabel = true,
    this.compact = false,
  });

  Color get _color {
    if (score >= 90) return HMColors.creditGold;
    if (score >= 75) return HMColors.creditGreen;
    if (score >= 60) return HMColors.creditBlue;
    if (score >= 40) return HMColors.creditOrange;
    return HMColors.creditRed;
  }

  String get _label {
    if (score >= 90) return '优质';
    if (score >= 75) return '良好';
    if (score >= 60) return '一般';
    if (score >= 40) return '偏低';
    return '风险';
  }

  @override
  Widget build(BuildContext context) {
    final color = _color;
    if (compact) {
      // 紧凑模式：只显示一个圆形 + 数字（适合嵌入文字行）
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(
            score.toStringAsFixed(1),
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w700,
              fontSize: 13,
            ),
          ),
        ],
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(HMRadius.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.verified, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            score.toStringAsFixed(1),
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w700,
              fontSize: 13,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          if (showLabel) ...[
            const SizedBox(width: 4),
            Text(
              _label,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
