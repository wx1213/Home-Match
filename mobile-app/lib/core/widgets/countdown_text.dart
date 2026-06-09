/// 倒计时文字 - 自动转红
library;

import 'package:flutter/material.dart';

import '../theme/app_tokens.dart';

class CountdownText extends StatefulWidget {
  final DateTime deadline;
  final TextStyle? style;
  final String expiredText;
  final bool showSeconds;

  const CountdownText({
    super.key,
    required this.deadline,
    this.style,
    this.expiredText = '已过期',
    this.showSeconds = true,
  });

  @override
  State<CountdownText> createState() => _CountdownTextState();
}

class _CountdownTextState extends State<CountdownText> {
  late Stream<DateTime> _ticker;

  @override
  void initState() {
    super.initState();
    _ticker = Stream.periodic(
      const Duration(seconds: 1),
      (_) => DateTime.now(),
    );
  }

  @override
  Widget build(BuildContext context) {
    final baseStyle = widget.style ?? Theme.of(context).textTheme.bodyMedium;
    return StreamBuilder<DateTime>(
      stream: _ticker,
      builder: (context, snapshot) {
        final now = DateTime.now();
        final diff = widget.deadline.difference(now);
        if (diff.isNegative) {
          return Text(
            widget.expiredText,
            style: baseStyle?.copyWith(color: HMColors.statusExpired),
          );
        }
        final urgent = diff.inHours < 1;
        final color = urgent ? HMColors.statusRejected : baseStyle?.color;
        return Text(
          _format(diff),
          style: baseStyle?.copyWith(
            color: color,
            fontWeight: urgent ? FontWeight.w700 : baseStyle.fontWeight,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        );
      },
    );
  }

  String _format(Duration d) {
    if (d.inDays >= 1) {
      return '剩余 ${d.inDays}天${d.inHours % 24}小时';
    }
    if (d.inHours >= 1) {
      return '剩余 ${d.inHours}:${(d.inMinutes % 60).toString().padLeft(2, '0')}'
          '${widget.showSeconds ? ":${(d.inSeconds % 60).toString().padLeft(2, '0')}" : ""}';
    }
    return '剩余 ${d.inMinutes}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';
  }
}
