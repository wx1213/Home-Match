/// 邀请详情 + 操作 - 按身份（buyer/seller）切换按钮
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/network/dio_client.dart';
import '../../core/theme/app_tokens.dart';
import '../../core/widgets/countdown_text.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/status_chip.dart';
import '../auth/auth_state.dart';
import 'invitation_models.dart';
import 'invitation_service.dart';

final _invitationDetailProvider =
    FutureProvider.autoDispose.family<Invitation, int>((ref, id) async {
  ref.watch(authProvider.select((a) => a.userId));
  return ref.read(invitationServiceProvider).getInvitation(id);
});

/// 邀请双方公开名片（buyer + seller）
class _PartyBrief {
  final int id;
  final String? displayName;
  final String? name;
  final double creditScore;
  const _PartyBrief({
    required this.id,
    required this.displayName,
    required this.name,
    required this.creditScore,
  });
}

/// 拉取买卖方两人的公开名片
final _partiesProvider =
    FutureProvider.autoDispose.family<List<_PartyBrief>, String>(
  (ref, idsKey) async {
    ref.watch(authProvider.select((a) => a.userId));
    if (idsKey.isEmpty) return const [];
    final resp = await ref.read(dioProvider).get(
      '/v1/users/batch',
      queryParameters: {'ids': idsKey},
    );
    final data = (resp.data['data'] as List).cast<Map<String, dynamic>>();
    return data
        .map((m) => _PartyBrief(
              id: m['id'] as int,
              displayName: m['display_name'] as String?,
              name: m['name'] as String?,
              creditScore: (m['credit_score'] as num?)?.toDouble() ?? 0,
            ))
        .toList();
  },
);

/// 角色枚举
enum _ViewerRole { buyer, seller, thirdParty }

_ViewerRole _resolveRole(Invitation inv, int? currentUserId) {
  if (currentUserId == null) return _ViewerRole.thirdParty;
  if (inv.buyerId == currentUserId) return _ViewerRole.buyer;
  if (inv.sellerId == currentUserId) return _ViewerRole.seller;
  return _ViewerRole.thirdParty;
}

class InvitationDetailScreen extends ConsumerWidget {
  final int invitationId;
  const InvitationDetailScreen({super.key, required this.invitationId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_invitationDetailProvider(invitationId));
    final color = Theme.of(context).colorScheme;
    final auth = ref.watch(authProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text('邀请 #$invitationId'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(_invitationDetailProvider(invitationId)),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorState(
          message: '$e',
          onRetry: () => ref.invalidate(_invitationDetailProvider(invitationId)),
        ),
        data: (inv) {
          final role = _resolveRole(inv, auth.userId);
          final meta = invitationStatusMeta(inv.status);
          return ListView(
            padding: const EdgeInsets.all(HMSpace.md),
            children: [
              // 头部状态卡
              Container(
                padding: const EdgeInsets.all(HMSpace.md),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [meta.color, meta.color.withValues(alpha: 0.7)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(HMRadius.lg),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 44,
                          height: 44,
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.25),
                            borderRadius: BorderRadius.circular(HMRadius.md),
                          ),
                          child: Icon(meta.icon, color: Colors.white, size: 24),
                        ),
                        const SizedBox(width: HMSpace.sm),
                        Expanded(
                          child: Text(
                            meta.label,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 22,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        // 身份徽章
                        _RoleChip(role: role),
                      ],
                    ),
                    const SizedBox(height: HMSpace.md),
                    if (inv.status == 'pending') ...[
                      const Text(
                        '倒计时',
                        style: TextStyle(color: Colors.white70, fontSize: 12),
                      ),
                      const SizedBox(height: 2),
                      CountdownText(
                        deadline: inv.expiredAt,
                        expiredText: '已超时',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ] else if (inv.proposalDeadline != null &&
                        inv.status == 'accepted') ...[
                      const Text(
                        '方案提交倒计时',
                        style: TextStyle(color: Colors.white70, fontSize: 12),
                      ),
                      const SizedBox(height: 2),
                      CountdownText(
                        deadline: inv.proposalDeadline!,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ] else if (inv.respondedAt != null) ...[
                      const Text(
                        '响应时间',
                        style: TextStyle(color: Colors.white70, fontSize: 12),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        DateFormat('MM-dd HH:mm').format(inv.respondedAt!.toLocal()),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: HMSpace.md),
              // 邀请信息
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(HMSpace.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.info_outline_rounded, size: 18, color: color.primary),
                          const SizedBox(width: 6),
                          const Text(
                            '邀请信息',
                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                      const SizedBox(height: HMSpace.sm),
                      KvRow(k: '需求 ID', v: '#${inv.demandId}'),
                      _PartyRow(
                        role: '买方',
                        roleColor: color.primary,
                        partyId: inv.buyerId,
                        partiesAsync: ref.watch(
                          _partiesProvider('${inv.buyerId},${inv.sellerId}'),
                        ),
                      ),
                      _PartyRow(
                        role: '卖方',
                        roleColor: HMColors.statusHandshaked,
                        partyId: inv.sellerId,
                        partiesAsync: ref.watch(
                          _partiesProvider('${inv.buyerId},${inv.sellerId}'),
                        ),
                      ),
                      KvRow(
                        k: '创建时间',
                        v: DateFormat('yyyy-MM-dd HH:mm').format(inv.createdAt.toLocal()),
                      ),
                      KvRow(
                        k: '过期时间',
                        v: DateFormat('yyyy-MM-dd HH:mm').format(inv.expiredAt.toLocal()),
                      ),
                      if (inv.note != null && inv.note!.isNotEmpty) ...[
                        const SizedBox(height: HMSpace.xs),
                        KvRow(k: '买方备注', v: inv.note!),
                      ],
                      if (inv.rejectReason != null) ...[
                        const SizedBox(height: HMSpace.xs),
                        KvRow(k: '拒绝原因', v: inv.rejectReason!),
                      ],
                    ],
                  ),
                ),
              ),
              // 查看方案入口（方案提交后双方都可见）
              if (inv.status == 'proposal_review' ||
                  inv.status == 'handshaked' ||
                  inv.status == 'closed') ...[
                const SizedBox(height: HMSpace.md),
                Card(
                  color: HMColors.statusProposal.withValues(alpha: 0.06),
                  child: ListTile(
                    leading: const Icon(
                      Icons.description_rounded,
                      color: HMColors.statusProposal,
                    ),
                    title: const Text(
                      '查看合作方案',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: const Text('卖方提交的方案全文 + 优势 + 看房建议'),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => context.push('/invitations/${inv.id}/proposal'),
                  ),
                ),
              ],
              // 跳到合作详情（已握手 / 已结束）
              if (inv.status == 'handshaked') ...[
                const SizedBox(height: HMSpace.md),
                Card(
                  color: HMColors.success.withValues(alpha: 0.08),
                  child: ListTile(
                    leading: const Icon(Icons.handshake_rounded, color: HMColors.success),
                    title: const Text('合作已建立', style: TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: const Text('查看合作详情 + 提交评价'),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => context.go('/cooperations'),
                  ),
                ),
              ],
              const SizedBox(height: 80), // 留出底部按钮空间
            ],
          );
        },
      ),
      // 底部操作按钮（按身份 + 状态切换）
      bottomNavigationBar: async.maybeWhen(
        data: (inv) => _buildActionBar(context, ref, inv, auth.userId),
        orElse: () => null,
      ),
    );
  }

  /// 根据身份 + 状态返回对应操作栏
  Widget? _buildActionBar(
    BuildContext context,
    WidgetRef ref,
    Invitation inv,
    int? currentUserId,
  ) {
    final role = _resolveRole(inv, currentUserId);
    if (role == _ViewerRole.thirdParty) {
      // 既不是 buyer 也不是 seller → 只能查看，没有操作权
      return null;
    }

    switch (inv.status) {
      // ============ PENDING ============
      case 'pending':
        if (role == _ViewerRole.seller) {
          return _BarWithTwoActions(
            primaryLabel: '接单',
            primaryIcon: Icons.check_rounded,
            onPrimary: () => _accept(context, ref, inv),
            secondaryLabel: '拒绝',
            secondaryIcon: Icons.close_rounded,
            onSecondary: () => _rejectAsSeller(context, ref, inv),
          );
        } else {
          // buyer：等卖方响应（无可用操作）
          return _ReadOnlyBar(
            text: '⏳ 等待卖方响应（24h 内未响应自动失效）',
            color: HMColors.statusPending,
          );
        }

      // ============ ACCEPTED（卖方已接单，待提交方案）============
      case 'accepted':
        if (role == _ViewerRole.seller) {
          return _BarWithSingleAction(
            label: '提交合作方案',
            icon: Icons.description_outlined,
            color: HMColors.statusAccepted,
            onTap: () =>
                context.push('/invitations/${inv.id}/proposal-new'),
          );
        } else {
          return _ReadOnlyBar(
            text: '⏳ 卖方已接单，2h 内提交方案',
            color: HMColors.statusAccepted,
          );
        }

      // ============ PROPOSAL_REVIEW（方案待审）============
      case 'proposal_review':
        if (role == _ViewerRole.buyer) {
          return _BarWithTwoActions(
            primaryLabel: '确认方案 → 握手',
            primaryIcon: Icons.handshake_rounded,
            onPrimary: () => _confirmProposal(context, ref, inv),
            secondaryLabel: '拒绝方案',
            secondaryIcon: Icons.close_rounded,
            secondaryColor: HMColors.statusRejected,
            onSecondary: () => _declineProposal(context, ref, inv),
          );
        } else {
          return _ReadOnlyBar(
            text: '⏳ 方案已提交，等待买方确认',
            color: HMColors.statusProposal,
          );
        }

      // ============ HANDSHAKED（已握手）============
      case 'handshaked':
        return _BarWithSingleAction(
          label: '查看合作详情',
          icon: Icons.handshake_rounded,
          color: HMColors.statusHandshaked,
          onTap: () => context.go('/cooperations'),
        );

      // ============ 终态：rejected / expired / closed ============
      default:
        return _ReadOnlyBar(
          text: '该邀请已结束，无可用操作',
          color: HMColors.statusExpired,
        );
    }
  }

  Future<void> _accept(BuildContext context, WidgetRef ref, Invitation inv) async {
    try {
      await ref.read(invitationServiceProvider).acceptInvitation(inv.id);
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('已接单！请在 2h 内提交方案'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } on DioException catch (e) {
      // 错误时也刷新一下，让 UI 反映真实状态
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) _showError(context, '操作失败', e);
    } catch (e) {
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('操作失败: $e'), behavior: SnackBarBehavior.floating),
        );
      }
    }
  }

  Future<void> _rejectAsSeller(
    BuildContext context,
    WidgetRef ref,
    Invitation inv,
  ) async {
    final reason = await showDialog<String>(
      context: context,
      builder: (_) => _ReasonDialog(title: '拒绝原因', hint: '简单说明（选填）'),
    );
    if (reason == null) return;
    try {
      await ref
          .read(invitationServiceProvider)
          .rejectInvitation(inv.id, reason: reason);
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('已拒绝'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } on DioException catch (e) {
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) _showError(context, '操作失败', e);
    } catch (e) {
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('操作失败: $e'), behavior: SnackBarBehavior.floating),
        );
      }
    }
  }

  Future<void> _confirmProposal(
    BuildContext context,
    WidgetRef ref,
    Invitation inv,
  ) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => _ConfirmDialog(
        title: '确认握手',
        content: '确认后将与卖方建立正式合作关系，握手后必须双方互评。是否继续？',
        confirmLabel: '确认握手',
        confirmColor: HMColors.statusHandshaked,
      ),
    );
    if (ok != true) return;
    try {
      final coop = await ref
          .read(invitationServiceProvider)
          .confirmProposal(inv.id);
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('🎉 握手成功！COOP-${coop.id}'),
            behavior: SnackBarBehavior.floating,
          ),
        );
        context.go('/cooperations/${coop.id}');
      }
    } on DioException catch (e) {
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) _showError(context, '握手失败', e);
    } catch (e) {
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('握手失败: $e'), behavior: SnackBarBehavior.floating),
        );
      }
    }
  }

  /// 统一错误提示：优先用后端 message（中文友好），再 fallback 到 dio 通用消息
  void _showError(BuildContext context, String prefix, DioException e) {
    String msg;
    final data = e.response?.data;
    if (data is Map && data['message'] is String) {
      msg = data['message'] as String;
    } else if (e.message != null) {
      msg = e.message!;
    } else {
      msg = '网络错误';
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$prefix: $msg'), behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _declineProposal(
    BuildContext context,
    WidgetRef ref,
    Invitation inv,
  ) async {
    final reason = await showDialog<String>(
      context: context,
      builder: (_) => _ReasonDialog(title: '拒绝方案', hint: '说明拒绝原因（选填）'),
    );
    if (reason == null) return;
    try {
      await ref
          .read(invitationServiceProvider)
          .declineProposal(inv.id, reason: reason);
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('已拒绝方案'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } on DioException catch (e) {
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) _showError(context, '操作失败', e);
    } catch (e) {
      ref.invalidate(_invitationDetailProvider(inv.id));
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('操作失败: $e'), behavior: SnackBarBehavior.floating),
        );
      }
    }
  }
}

// ============================================================
//  底部操作栏的 3 种形态
// ============================================================

class _BarWithTwoActions extends StatelessWidget {
  final String primaryLabel;
  final IconData primaryIcon;
  final VoidCallback onPrimary;
  final String secondaryLabel;
  final IconData secondaryIcon;
  final VoidCallback onSecondary;
  final Color? secondaryColor;

  const _BarWithTwoActions({
    required this.primaryLabel,
    required this.primaryIcon,
    required this.onPrimary,
    required this.secondaryLabel,
    required this.secondaryIcon,
    required this.onSecondary,
    this.secondaryColor,
  });

  @override
  Widget build(BuildContext context) {
    final c = secondaryColor;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(HMSpace.md),
        child: Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                icon: Icon(secondaryIcon, size: 18),
                label: Text(secondaryLabel),
                style: OutlinedButton.styleFrom(
                  foregroundColor: c,
                  side: c != null
                      ? BorderSide(color: c.withValues(alpha: 0.3))
                      : null,
                ),
                onPressed: onSecondary,
              ),
            ),
            const SizedBox(width: HMSpace.sm),
            Expanded(
              flex: 2,
              child: FilledButton.icon(
                icon: Icon(primaryIcon, size: 18),
                label: Text(primaryLabel),
                onPressed: onPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BarWithSingleAction extends StatelessWidget {
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;
  const _BarWithSingleAction({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(HMSpace.md),
        child: FilledButton.icon(
          icon: Icon(icon, size: 18),
          label: Text(label),
          style: FilledButton.styleFrom(
            backgroundColor: color,
            foregroundColor: Colors.white,
          ),
          onPressed: onTap,
        ),
      ),
    );
  }
}

class _ReadOnlyBar extends StatelessWidget {
  final String text;
  final Color color;
  const _ReadOnlyBar({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Container(
        margin: const EdgeInsets.all(HMSpace.md),
        padding: const EdgeInsets.symmetric(horizontal: HMSpace.md, vertical: HMSpace.sm),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(HMRadius.md),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.info_outline_rounded, size: 16, color: color),
            const SizedBox(width: 6),
            Flexible(
              child: Text(
                text,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: color,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
//  身份徽章（在头部状态卡右上角）
// ============================================================

class _RoleChip extends StatelessWidget {
  final _ViewerRole role;
  const _RoleChip({required this.role});

  @override
  Widget build(BuildContext context) {
    if (role == _ViewerRole.thirdParty) return const SizedBox.shrink();
    final isBuyer = role == _ViewerRole.buyer;
    final label = isBuyer ? '我是买方' : '我是卖方';
    final icon = isBuyer ? Icons.shopping_cart_outlined : Icons.storefront_outlined;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.25),
        borderRadius: BorderRadius.circular(HMRadius.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: Colors.white),
          const SizedBox(width: 4),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================
//  通用对话框
// ============================================================

class KvRow extends StatelessWidget {
  final String k;
  final String v;
  const KvRow({super.key, required this.k, required this.v});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 72,
            child: Text(
              k,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                fontSize: 13,
              ),
            ),
          ),
          Expanded(
            child: Text(
              v,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReasonDialog extends StatefulWidget {
  final String title;
  final String hint;
  const _ReasonDialog({required this.title, required this.hint});

  @override
  State<_ReasonDialog> createState() => _ReasonDialogState();
}

class _ReasonDialogState extends State<_ReasonDialog> {
  final _ctl = TextEditingController();

  @override
  void dispose() {
    _ctl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: TextField(
        controller: _ctl,
        maxLines: 3,
        decoration: InputDecoration(hintText: widget.hint),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('取消'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(_ctl.text),
          child: const Text('确认'),
        ),
      ],
    );
  }
}

class _ConfirmDialog extends StatelessWidget {
  final String title;
  final String content;
  final String confirmLabel;
  final Color confirmColor;
  const _ConfirmDialog({
    required this.title,
    required this.content,
    required this.confirmLabel,
    required this.confirmColor,
  });

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(title),
      content: Text(content),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('取消'),
        ),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: confirmColor),
          onPressed: () => Navigator.of(context).pop(true),
          child: Text(confirmLabel),
        ),
      ],
    );
  }
}

/// 邀请信息里的"买方" / "卖方" 行 - 显示真实名字
class _PartyRow extends StatelessWidget {
  final String role; // "买方" or "卖方"
  final Color roleColor;
  final int partyId;
  final AsyncValue<List<_PartyBrief>> partiesAsync;

  const _PartyRow({
    required this.role,
    required this.roleColor,
    required this.partyId,
    required this.partiesAsync,
  });

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 72,
            child: Text(
              role,
              style: TextStyle(
                color: color.onSurface.withValues(alpha: 0.6),
                fontSize: 13,
              ),
            ),
          ),
          Expanded(
            child: partiesAsync.when(
              data: (list) {
                final party = list.firstWhere(
                  (p) => p.id == partyId,
                  orElse: () => _PartyBrief(
                    id: partyId,
                    displayName: null,
                    name: null,
                    creditScore: 0,
                  ),
                );
                return _PartyChip(party: party, roleColor: roleColor);
              },
              loading: () => Text(
                '加载中… #$partyId',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
              ),
              error: (_, __) => Text(
                '#$partyId',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// 显示一个买卖方 chip（头像 + 名字 + 信用分）
class _PartyChip extends StatelessWidget {
  final _PartyBrief party;
  final Color roleColor;
  const _PartyChip({required this.party, required this.roleColor});

  @override
  Widget build(BuildContext context) {
    final display = party.displayName ?? party.name ?? '用户 #${party.id}';
    return Row(
      children: [
        HMUserAvatar(name: display, size: 24),
        const SizedBox(width: 6),
        Text(
          display,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        ),
        if (party.creditScore > 0) ...[
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: roleColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(HMRadius.sm),
            ),
            child: Text(
              '信用 ${party.creditScore.toStringAsFixed(1)}',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: roleColor,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
        ],
      ],
    );
  }
}
