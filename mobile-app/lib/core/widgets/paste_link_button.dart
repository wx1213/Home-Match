/// 粘贴贝壳链接按钮（P0 任务 1 - B2 commit）
///
/// UI：
/// - 默认状态：OutlinedButton.icon(Icons.paste) "粘贴贝壳链接"
/// - 点击 → 读取剪贴板 → 调 beikeParseService.parse()
///   - 成功：显示预览卡片（"✓ 北京-二手房 #12345"），触发 onParsed 回调
///   - 失败：显示错误提示（红色文字 + SnackBar），保留用户手动粘贴能力
///
/// 用法：
/// ```dart
/// PasteLinkButton(
///   onParsed: (url, result) {
///     _sourceUrlCtl.text = url;
///     setState(() => _parsedInfo = result);
///   },
/// )
/// ```
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../network/api_exception.dart';
import '../network/beike_parse_service.dart';
import '../theme/app_tokens.dart';

class PasteLinkButton extends ConsumerStatefulWidget {
  const PasteLinkButton({
    super.key,
    required this.onParsed,
    this.hint = '粘贴贝壳链接',
    this.buttonLabel = '粘贴贝壳链接',
  });

  /// 解析成功回调。参数：原始 URL + 解析结果。
  /// 表单收到后把 URL 写入 sourceUrl 字段，result 用于展示预览卡片。
  final void Function(String url, BeikeParseResult result) onParsed;

  /// 用户手动粘贴的提示文案
  final String hint;

  /// 按钮文案
  final String buttonLabel;

  @override
  ConsumerState<PasteLinkButton> createState() => _PasteLinkButtonState();
}

class _PasteLinkButtonState extends ConsumerState<PasteLinkButton> {
  bool _busy = false;

  Future<void> _handlePaste() async {
    setState(() => _busy = true);
    try {
      // 1. 读取剪贴板
      final clipData = await Clipboard.getData('text/plain');
      final url = clipData?.text?.trim();

      if (url == null || url.isEmpty) {
        _showError('剪贴板为空，请先复制贝壳链接');
        return;
      }

      // 2. 调后端解析
      final service = ref.read(beikeParseServiceProvider);
      final result = await service.parse(url);

      if (!mounted) return;

      if (!result.valid) {
        _showError(result.reason ?? '链接格式无效');
        return;
      }

      // 3. 成功 → 回调
      widget.onParsed(url, result);
    } on ApiException catch (e) {
      _showError(e.message);
    } catch (e) {
      _showError('解析失败: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: HMColors.error,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: _busy ? null : _handlePaste,
      icon: _busy
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.paste_rounded, size: 18),
      label: Text(_busy ? '解析中...' : widget.buttonLabel),
      style: OutlinedButton.styleFrom(
        padding: const EdgeInsets.symmetric(
          horizontal: HMSpace.md,
          vertical: HMSpace.sm,
        ),
      ),
    );
  }
}

/// 解析成功的预览卡片（可选组件，给表单复用）
class BeikePreviewCard extends StatelessWidget {
  const BeikePreviewCard({
    super.key,
    required this.url,
    required this.result,
    this.onClear,
  });

  final String url;
  final BeikeParseResult result;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    if (!result.valid) return const SizedBox.shrink();

    return Container(
      padding: const EdgeInsets.all(HMSpace.sm),
      decoration: BoxDecoration(
        color: HMColors.success.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(HMRadius.sm),
        border: Border.all(color: HMColors.success.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.check_circle_rounded, color: HMColors.success, size: 18),
          const SizedBox(width: HMSpace.xs),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '✓ 已识别 ${result.previewLabel ?? "贝壳链接"}',
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: HMColors.success,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  url,
                  style: TextStyle(
                    fontSize: 11,
                    color: HMColors.success.withValues(alpha: 0.7),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          if (onClear != null)
            IconButton(
              icon: const Icon(Icons.close_rounded, size: 18),
              onPressed: onClear,
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(),
            ),
        ],
      ),
    );
  }
}