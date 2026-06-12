/// 提交合作方案表单（卖方接单后 2h 内）
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_tokens.dart';
import 'invitation_service.dart';

class ProposalFormScreen extends ConsumerStatefulWidget {
  final int invitationId;
  const ProposalFormScreen({super.key, required this.invitationId});

  @override
  ConsumerState<ProposalFormScreen> createState() => _ProposalFormScreenState();
}

class _ProposalFormScreenState extends ConsumerState<ProposalFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _contentCtl = TextEditingController();
  final _fitPointsCtl = TextEditingController();
  final _viewingCtl = TextEditingController();
  final _ownerCtl = TextEditingController();
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _contentCtl.dispose();
    _fitPointsCtl.dispose();
    _viewingCtl.dispose();
    _ownerCtl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await ref.read(invitationServiceProvider).submitProposal(
            widget.invitationId,
            content: _contentCtl.text.trim(),
            fitPoints: _fitPointsCtl.text.trim().isEmpty
                ? null
                : _fitPointsCtl.text.trim(),
            viewingSuggestion: _viewingCtl.text.trim().isEmpty
                ? null
                : _viewingCtl.text.trim(),
            ownerSituation: _ownerCtl.text.trim().isEmpty
                ? null
                : _ownerCtl.text.trim(),
          );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('方案已提交，等待买方确认'),
            behavior: SnackBarBehavior.floating,
          ),
        );
        // 跳到方案详情页
        context.go('/invitations/${widget.invitationId}/proposal');
      }
    } catch (e) {
      setState(() {
        _error = '提交失败: $e';
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text('提交合作方案'),
        actions: [
          IconButton(
            tooltip: '查看示例',
            icon: const Icon(Icons.lightbulb_outline_rounded),
            onPressed: () => _showExampleDialog(context),
          ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(HMSpace.md),
          children: [
            // 头部说明
            Container(
              padding: const EdgeInsets.all(HMSpace.md),
              decoration: BoxDecoration(
                color: color.primaryContainer.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(HMRadius.md),
              ),
              child: Row(
                children: [
                  Icon(Icons.info_outline_rounded,
                      size: 18, color: color.primary),
                  const SizedBox(width: HMSpace.xs),
                  const Expanded(
                    child: Text(
                      '方案需 2h 内提交。提交后买方会收到通知并决定是否握手。',
                      style: TextStyle(fontSize: 12),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: HMSpace.md),

            // 必填：方案内容
            _SectionTitle(title: '方案内容 *', hint: '建议 100-500 字'),
            const SizedBox(height: HMSpace.xs),
            TextFormField(
              controller: _contentCtl,
              maxLines: 6,
              minLines: 4,
              decoration: const InputDecoration(
                hintText: '例如：\n• 匹配点：总价/位置/户型都符合\n• 推荐房源：xxx 小区 3 室 1 厅\n• 业主情况：自住，诚意出售',
              ),
              validator: (v) {
                if (v == null || v.trim().length < 20) {
                  return '方案内容至少 20 字';
                }
                return null;
              },
            ),
            const SizedBox(height: HMSpace.md),

            // 选填：卖方优势
            _SectionTitle(
                title: '卖方优势',
                hint: '为什么客户应该选你？'),
            const SizedBox(height: HMSpace.xs),
            TextFormField(
              controller: _fitPointsCtl,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: '例如：深耕本板块 8 年，熟悉 30+ 小区',
              ),
            ),
            const SizedBox(height: HMSpace.md),

            // 选填：看房建议
            _SectionTitle(title: '看房建议', hint: '什么时候看房比较好？'),
            const SizedBox(height: HMSpace.xs),
            TextFormField(
              controller: _viewingCtl,
              maxLines: 2,
              decoration: const InputDecoration(
                hintText: '例如：建议周五晚 8 点集中看房，约 2-3 套',
              ),
            ),
            const SizedBox(height: HMSpace.md),

            // 选填：业主情况
            _SectionTitle(title: '业主情况', hint: '业主卖房意愿 / 紧迫度'),
            const SizedBox(height: HMSpace.xs),
            TextFormField(
              controller: _ownerCtl,
              maxLines: 3,
              decoration: const InputDecoration(
                hintText: '例如：业主已购新房，急售；可议价空间 5%',
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
                        style: TextStyle(
                            color: color.onErrorContainer, fontSize: 13),
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
              label: Text(_submitting ? '提交中...' : '提交方案'),
            ),
            const SizedBox(height: HMSpace.xl),
          ],
        ),
      ),
    );
  }

  void _showExampleDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('方案示例'),
        content: const SingleChildScrollView(
          child: Text(
            '【匹配点】\n'
            '• 总价 580w 在客户预算 500-600w 范围内\n'
            '• 户型 3 室 1 厅，78㎡，满足刚需\n'
            '• 双井板块，靠近地铁 7 号线\n\n'
            '【推荐房源】\n'
            '1. 双井富力城 A 区 - 580w，业主诚心\n'
            '2. 劲松九区 - 520w，性价比高\n'
            '3. 垂杨柳南里 - 555w，配套齐全\n\n'
            '【业主情况】\n'
            '业主已购新房，急售；议价空间 3-5%。\n'
            '看房灵活，配合度高。',
            style: TextStyle(fontSize: 13, height: 1.6),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('知道了'),
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final String? hint;
  const _SectionTitle({required this.title, this.hint});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        if (hint != null) ...[
          const SizedBox(width: 6),
          Text(
            hint!,
            style: TextStyle(
              fontSize: 11,
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
            ),
          ),
        ],
      ],
    );
  }
}
