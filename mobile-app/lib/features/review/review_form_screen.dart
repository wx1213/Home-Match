/// 评价表单 - 评分 + 标签 + 评价后回跳
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:dio/dio.dart';

import '../../core/network/dio_client.dart';
import '../../core/theme/app_tokens.dart';
import '../auth/auth_state.dart';
import '../cooperation/cooperation_service.dart';
import '../cooperation/cooperation_models.dart';

class ReviewFormScreen extends ConsumerStatefulWidget {
  final int cooperationId;
  const ReviewFormScreen({super.key, required this.cooperationId});

  @override
  ConsumerState<ReviewFormScreen> createState() => _ReviewFormScreenState();
}

/// 拉取合作信息（用于判断我是买方还是卖方）
final _coopForReviewProvider =
    FutureProvider.autoDispose.family<Cooperation, int>((ref, coopId) async {
  ref.watch(authProvider.select((a) => a.userId));
  return ref.read(cooperationServiceProvider).get(coopId);
});

class _ReviewFormScreenState extends ConsumerState<ReviewFormScreen> {
  int _rating = 5;
  final _selectedTags = <String>{};
  final _commentCtl = TextEditingController();
  bool _anonymous = false;
  bool _submitting = false;
  String? _error;

  /// 我是买方时评价的标签（评价卖方）
  static const _tagGroupsAsBuyer = <String, List<String>>{
    '房源': ['房源真实', '描述准确', '实勘靠谱', '业主配合'],
    '服务': ['响应及时', '热情耐心', '带看高效', '专业讲解'],
    '合作': ['流程规范', '后续跟进', '议价合理', '愿意复购'],
  };

  /// 我是卖方时评价的标签（评价买方）
  static const _tagGroupsAsSeller = <String, List<String>>{
    '客户': ['客户爽快', '决策快', '预算明确', '议价合理'],
    '合作': ['守时守约', '尊重专业', '沟通顺畅', '配合度高'],
    '后续': ['回访及时', '付款及时', '口碑好', '愿意复购'],
  };

  /// 根据 user 角色取对应标签
  Map<String, List<String>> get _tagGroups {
    return _isBuyer ? _tagGroupsAsBuyer : _tagGroupsAsSeller;
  }

  /// 当前用户在此合作中的角色
  bool get _isBuyer {
    final myId = ref.read(authProvider).userId;
    final coop = ref.watch(_coopForReviewProvider(widget.cooperationId)).valueOrNull;
    if (myId == null || coop == null) return true; // 默认买方
    return myId == coop.buyerId;
  }

  /// 合作信息
  Cooperation? get _coop {
    return ref.watch(_coopForReviewProvider(widget.cooperationId)).valueOrNull;
  }

  @override
  void dispose() {
    _commentCtl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await ref.read(dioProvider).post(
            '/v1/cooperations/${widget.cooperationId}/review',
            data: {
              'rating': _rating,
              'comment': _commentCtl.text.isEmpty ? null : _commentCtl.text,
              'is_anonymous': _anonymous,
              if (_selectedTags.isNotEmpty) 'tags': _selectedTags.toList(),
            },
          );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('评价已提交，谢谢！'),
            behavior: SnackBarBehavior.floating,
          ),
        );
        // 替换当前路由，避免返回时再次进入表单
        context.go('/cooperations/${widget.cooperationId}');
      }
    } on DioException catch (e) {
      setState(() {
        _error = '提交失败: ${e.response?.data?['message'] ?? e.message}';
        _submitting = false;
      });
    } catch (e) {
      setState(() {
        _error = '提交失败: $e';
        _submitting = false;
      });
    }
  }

  String _ratingHint() {
    switch (_rating) {
      case 5:
        return '非常满意，强烈推荐';
      case 4:
        return '比较满意，可以合作';
      case 3:
        return '一般般，凑合能用';
      case 2:
        return '不太满意，体验差';
      case 1:
        return '极差，强烈不建议';
      default:
        return '请选择评分';
    }
  }

  Color _ratingColor() {
    if (_rating >= 4) return HMColors.success;
    if (_rating >= 3) return HMColors.statusPending;
    return HMColors.statusRejected;
  }

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final coop = _coop;
    final isBuyer = _isBuyer;
    return Scaffold(
      appBar: AppBar(
        title: Text(isBuyer ? '评价卖方' : '评价买方'),
        actions: [
          // 切换角色提示（dev 调试用）
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(_coopForReviewProvider(widget.cooperationId)),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(HMSpace.md),
        children: [
          // 角色说明
          if (coop != null) ...[
            Container(
              padding: const EdgeInsets.all(HMSpace.md),
              decoration: BoxDecoration(
                color: (isBuyer ? color.primary : HMColors.statusHandshaked)
                    .withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(HMRadius.md),
              ),
              child: Row(
                children: [
                  Icon(
                    isBuyer ? Icons.storefront_rounded : Icons.shopping_cart_rounded,
                    color: isBuyer ? color.primary : HMColors.statusHandshaked,
                    size: 20,
                  ),
                  const SizedBox(width: HMSpace.xs),
                  Expanded(
                    child: Text(
                      isBuyer
                          ? '作为买方，评价此次合作的卖方（#${coop.sellerId}）'
                          : '作为卖方，评价此次合作的买方（#${coop.buyerId}）',
                      style: TextStyle(
                        fontSize: 13,
                        color: color.onSurface,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: HMSpace.md),
          ],
          // 评分
          Card(
            child: Padding(
              padding: const EdgeInsets.all(HMSpace.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const Text(
                    '请为此次合作打分',
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: HMSpace.md),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(5, (i) {
                      final v = i + 1;
                      return IconButton(
                        iconSize: 44,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(minWidth: 44, minHeight: 44),
                        icon: Icon(
                          v <= _rating ? Icons.star_rounded : Icons.star_outline_rounded,
                          color: v <= _rating ? Colors.amber.shade600 : color.onSurface.withValues(alpha: 0.3),
                        ),
                        onPressed: () => setState(() => _rating = v),
                      );
                    }),
                  ),
                  const SizedBox(height: HMSpace.xs),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      color: _ratingColor().withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(HMRadius.full),
                    ),
                    child: Text(
                      '$_rating 星 · ${_ratingHint()}',
                      style: TextStyle(
                        color: _ratingColor(),
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: HMSpace.md),
          // 标签
          Card(
            child: Padding(
              padding: const EdgeInsets.all(HMSpace.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.tag_rounded, size: 16, color: color.primary),
                      const SizedBox(width: 6),
                      const Text(
                        '快速标签（可多选）',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: HMSpace.sm),
                  ..._tagGroups.entries.map(
                    (entry) => Padding(
                      padding: const EdgeInsets.only(bottom: HMSpace.xs),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            entry.key,
                            style: TextStyle(
                              fontSize: 11,
                              color: color.onSurface.withValues(alpha: 0.6),
                            ),
                          ),
                          const SizedBox(height: 4),
                          Wrap(
                            spacing: 6,
                            runSpacing: 6,
                            children: entry.value
                                .map(
                                  (t) => FilterChip(
                                    label: Text(t, style: const TextStyle(fontSize: 12)),
                                    selected: _selectedTags.contains(t),
                                    onSelected: (sel) => setState(() {
                                      if (sel) {
                                        _selectedTags.add(t);
                                      } else {
                                        _selectedTags.remove(t);
                                      }
                                    }),
                                  ),
                                )
                                .toList(),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: HMSpace.md),
          // 文字评价
          Card(
            child: Padding(
              padding: const EdgeInsets.all(HMSpace.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.edit_note_rounded, size: 16, color: color.primary),
                      const SizedBox(width: 6),
                      const Text(
                        '详细评价（选填）',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: HMSpace.sm),
                  TextField(
                    controller: _commentCtl,
                    maxLines: 5,
                    maxLength: 500,
                    decoration: const InputDecoration(
                      hintText: '说说这次合作的感受、亮点或建议...',
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: HMSpace.md),
          // 匿名开关
          Card(
            child: SwitchListTile(
              title: const Text('匿名评价'),
              subtitle: const Text('开启后，您的姓名对其他用户隐藏'),
              value: _anonymous,
              onChanged: (v) => setState(() => _anonymous = v),
              contentPadding: const EdgeInsets.symmetric(horizontal: HMSpace.md),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: HMSpace.md),
            Container(
              padding: const EdgeInsets.all(HMSpace.sm),
              decoration: BoxDecoration(
                color: color.errorContainer.withValues(alpha: 0.6),
                borderRadius: BorderRadius.circular(HMRadius.sm),
              ),
              child: Row(
                children: [
                  Icon(Icons.error_outline, color: color.error, size: 18),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      _error!,
                      style: TextStyle(color: color.onErrorContainer, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: HMSpace.lg),
          FilledButton.icon(
            onPressed: _submitting ? null : _submit,
            icon: _submitting
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.send_rounded, size: 18),
            label: Text(_submitting ? '提交中...' : '提交评价'),
          ),
          const SizedBox(height: HMSpace.xl),
        ],
      ),
    );
  }
}
