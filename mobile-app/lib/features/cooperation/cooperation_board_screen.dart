/// 合作仪表板 - 统一展示合作 + 邀请 + 评价
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_tokens.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/status_chip.dart';
import '../invitation/invitation_models.dart';
import '../invitation/invitation_service.dart';
import '../auth/auth_state.dart';
import '../property/property_service.dart';
import '../demand/demand_service.dart';
import 'cooperation_models.dart';
import 'cooperation_service.dart';
import 'widgets/invitation_card.dart';

// ============================================================
//  Providers - 都 watch authProvider.userId，切换身份时自动重算
// ============================================================

final _cooperationsProvider = FutureProvider.autoDispose<List<Cooperation>>((ref) async {
  ref.watch(authProvider.select((a) => a.userId));
  return ref.read(cooperationServiceProvider).listMy();
});

final _myInvitationsProvider =
    FutureProvider.autoDispose.family<List<Invitation>, String>(
  (ref, role) {
    ref.watch(authProvider.select((a) => a.userId));
    return ref.read(invitationServiceProvider).listMyInvitations(role: role);
  },
);

/// 用户身份（用于空状态文案）
enum _UserRole { buyer, seller, both, neither, unknown }

Future<_UserRole> _detectRole(WidgetRef ref) async {
  try {
    final props = await ref.read(propertyServiceProvider).listMyProperties();
    final dems = await ref.read(demandServiceProvider).listMyDemands();
    final hasProps = props.isNotEmpty;
    final hasDems = dems.isNotEmpty;
    if (hasProps && hasDems) return _UserRole.both;
    if (hasProps) return _UserRole.seller;
    if (hasDems) return _UserRole.buyer;
    return _UserRole.neither;
  } catch (_) {
    return _UserRole.unknown;
  }
}

// ============================================================
//  主屏幕
// ============================================================

class CooperationBoardScreen extends ConsumerWidget {
  const CooperationBoardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final coopsAsync = ref.watch(_cooperationsProvider);
    final myInvBuyer = ref.watch(_myInvitationsProvider('buyer'));
    final myInvSeller = ref.watch(_myInvitationsProvider('seller'));
    final color = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('合作'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () {
              ref.invalidate(_cooperationsProvider);
              ref.invalidate(_myInvitationsProvider);
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(_cooperationsProvider);
          ref.invalidate(_myInvitationsProvider);
          await Future.wait([
            ref.read(_cooperationsProvider.future),
            ref.read(_myInvitationsProvider('buyer').future),
            ref.read(_myInvitationsProvider('seller').future),
          ]);
        },
        child: coopsAsync.when(
          loading: () => const _LoadingState(),
          error: (e, _) => ErrorState(
            message: '$e',
            onRetry: () => ref.invalidate(_cooperationsProvider),
          ),
          data: (coops) {
            // 计算分组
            final myBuyerInvs = myInvBuyer.maybeWhen(
              data: (list) => list,
              orElse: () => const <Invitation>[],
            );
            final mySellerInvs = myInvSeller.maybeWhen(
              data: (list) => list,
              orElse: () => const <Invitation>[],
            );

            final pendingInvs = [
              ...myBuyerInvs.where((i) =>
                  i.status == 'pending' ||
                  i.status == 'accepted' ||
                  i.status == 'proposal_review'),
              ...mySellerInvs.where((i) =>
                  i.status == 'pending' ||
                  i.status == 'accepted' ||
                  i.status == 'proposal_review'),
            ];

            final activeCoops =
                coops.where((c) => c.status != 'completed' && c.status != 'terminated').toList();
            final archivedCoops = coops
                .where((c) => c.status == 'completed' || c.status == 'terminated')
                .toList();

            return CustomScrollView(
              slivers: [
                const SliverToBoxAdapter(child: SizedBox(height: HMSpace.sm)),

                // ====== 数据概览 ======
                SliverToBoxAdapter(
                  child: _OverviewBar(
                    pendingInvs: pendingInvs,
                    activeCoops: activeCoops,
                  ),
                ),

                // ====== 进行中的合作 ======
                if (activeCoops.isNotEmpty) ...[
                  const SliverToBoxAdapter(child: SizedBox(height: HMSpace.md)),
                  SliverToBoxAdapter(
                    child: _SectionHeader(
                      icon: Icons.handshake_rounded,
                      title: '进行中的合作',
                      badge: '${activeCoops.length}',
                    ),
                  ),
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(
                        HMSpace.md, HMSpace.xs, HMSpace.md, 0),
                    sliver: SliverList.separated(
                      itemCount: activeCoops.length,
                      separatorBuilder: (_, __) => const SizedBox(height: HMSpace.xs),
                      itemBuilder: (_, i) => _CooperationCard(coop: activeCoops[i]),
                    ),
                  ),
                ],

                // ====== 我发出的邀请 ======
                ..._buildInvSection(
                  context: context,
                  title: '我发出的邀请',
                  icon: Icons.send_rounded,
                  iconColor: color.primary,
                  list: myBuyerInvs
                      .where((i) =>
                          i.status == 'pending' ||
                          i.status == 'accepted' ||
                          i.status == 'proposal_review')
                      .toList(),
                  isOutgoing: true,
                ),
                // ====== 我收到的邀请 ======
                ..._buildInvSection(
                  context: context,
                  title: '我收到的邀请',
                  icon: Icons.inbox_rounded,
                  iconColor: HMColors.statusHandshaked,
                  list: mySellerInvs
                      .where((i) =>
                          i.status == 'pending' ||
                          i.status == 'accepted' ||
                          i.status == 'proposal_review')
                      .toList(),
                  isOutgoing: false,
                ),

                // ====== 空状态 ======
                if (activeCoops.isEmpty && pendingInvs.isEmpty) ...[
                  const SliverToBoxAdapter(child: SizedBox(height: HMSpace.xl)),
                  SliverToBoxAdapter(
                    child: _EmptyDashboard(),
                  ),
                ],

                // ====== 历史合作（折叠） ======
                if (archivedCoops.isNotEmpty) ...[
                  const SliverToBoxAdapter(child: SizedBox(height: HMSpace.md)),
                  SliverToBoxAdapter(
                    child: _ArchiveSection(coops: archivedCoops),
                  ),
                ],

                const SliverToBoxAdapter(child: SizedBox(height: HMSpace.xl)),
              ],
            );
          },
        ),
      ),
    );
  }
}

// ============================================================
//  概览（4 个数字）
// ============================================================

/// 渲染一个邀请 section（我发出的 / 我收到的）
List<Widget> _buildInvSection({
  required BuildContext context,
  required String title,
  required IconData icon,
  required Color iconColor,
  required List<Invitation> list,
  required bool isOutgoing,
}) {
  // 已经在调用方 build() 里取过 color，这里不需要
  if (list.isEmpty) return const [];
  return [
    SliverToBoxAdapter(child: const SizedBox(height: HMSpace.md)),
    SliverToBoxAdapter(
      child: _SectionHeader(
        icon: icon,
        title: title,
        badge: '${list.length}',
        iconColor: iconColor,
      ),
    ),
    SliverPadding(
      padding: const EdgeInsets.fromLTRB(HMSpace.md, HMSpace.xs, HMSpace.md, 0),
      sliver: SliverList.separated(
        itemCount: list.length,
        separatorBuilder: (_, __) => const SizedBox(height: HMSpace.xs),
        itemBuilder: (_, i) => _InvitationCard(inv: list[i], isOutgoing: isOutgoing),
      ),
    ),
  ];
}

class _OverviewBar extends StatelessWidget {
  final List<Invitation> pendingInvs;
  final List<Cooperation> activeCoops;
  const _OverviewBar({required this.pendingInvs, required this.activeCoops});

  @override
  Widget build(BuildContext context) {
    final pendingCount = pendingInvs.length;
    final proposalCount =
        pendingInvs.where((i) => i.status == 'proposal_review').length;
    final coopsCount = activeCoops.length;
    final needReview = activeCoops
        .where((c) => !(c.buyerReviewed && c.sellerReviewed))
        .length;

    return Padding(
      padding: const EdgeInsets.fromLTRB(
        HMSpace.md, 0, HMSpace.md, 0,
      ),
      child: Row(
        children: [
          _StatChip(
            value: pendingCount,
            label: '进行中邀请',
            color: HMColors.statusPending,
            icon: Icons.send_rounded,
          ),
          const SizedBox(width: HMSpace.xs),
          _StatChip(
            value: proposalCount,
            label: '方案待审',
            color: HMColors.statusProposal,
            icon: Icons.description_rounded,
          ),
          const SizedBox(width: HMSpace.xs),
          _StatChip(
            value: coopsCount,
            label: '合作中',
            color: HMColors.statusHandshaked,
            icon: Icons.handshake_rounded,
          ),
          const SizedBox(width: HMSpace.xs),
          _StatChip(
            value: needReview,
            label: '待评价',
            color: HMColors.warmGradient.colors.first,
            icon: Icons.star_border_rounded,
          ),
        ],
      ),
    );
  }
}

class _StatChip extends StatelessWidget {
  final int value;
  final String label;
  final Color color;
  final IconData icon;
  const _StatChip({
    required this.value,
    required this.label,
    required this.color,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: HMSpace.sm, horizontal: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(HMRadius.md),
        ),
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, size: 14, color: color),
                const SizedBox(width: 4),
                Text(
                  '$value',
                  style: TextStyle(
                    color: color,
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
//  段头
// ============================================================

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? badge;
  final Color? iconColor;
  const _SectionHeader({
    required this.icon,
    required this.title,
    this.badge,
    this.iconColor,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        HMSpace.md + 2, HMSpace.md, HMSpace.md + 2, HMSpace.xs,
      ),
      child: Row(
        children: [
          Icon(icon, size: 16, color: iconColor ?? Theme.of(context).colorScheme.primary),
          const SizedBox(width: 6),
          Text(
            title,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
          if (badge != null) ...[
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary,
                borderRadius: BorderRadius.circular(HMRadius.full),
              ),
              child: Text(
                badge!,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ============================================================
//  合作卡片
// ============================================================

class _CooperationCard extends ConsumerWidget {
  final Cooperation coop;
  const _CooperationCard({required this.coop});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = Theme.of(context).colorScheme;
    final meta = cooperationStatusMeta(coop.status);
    final fmt = DateFormat('MM-dd HH:mm');
    // 当前用户在此合作中的身份
    final myId = ref.read(authProvider).userId;
    final iAmBuyer = myId == coop.buyerId;
    final iAmSeller = myId == coop.sellerId;
    final isParticipant = iAmBuyer || iAmSeller;
    // 当前用户对哪一方打分
    final opponentRole = iAmBuyer ? '卖方' : (iAmSeller ? '买方' : null);
    // 我（当前用户）实际评价状态
    final iHaveReviewed = iAmBuyer
        ? coop.buyerReviewed
        : (iAmSeller ? coop.sellerReviewed : true);
    // 对方是否已评（保留供扩展：详情页"对方已评"显示用）
    // ignore: unused_local_variable
    final opponentReviewed = iAmBuyer
        ? coop.sellerReviewed
        : (iAmSeller ? coop.buyerReviewed : false);

    return Card(
      child: InkWell(
        onTap: () => context.push('/cooperations/${coop.id}'),
        borderRadius: BorderRadius.circular(HMRadius.lg),
        child: Padding(
          padding: const EdgeInsets.all(HMSpace.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [color.primary, color.primary.withValues(alpha: 0.7)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(HMRadius.sm),
                    ),
                    child: const Icon(Icons.handshake_rounded, color: Colors.white, size: 22),
                  ),
                  const SizedBox(width: HMSpace.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'COOP-${coop.id}',
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            fontFeatures: [FontFeature.tabularFigures()],
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          fmt.format(coop.signedAt.toLocal()),
                          style: TextStyle(
                            fontSize: 11,
                            color: color.onSurface.withValues(alpha: 0.6),
                          ),
                        ),
                      ],
                    ),
                  ),
                  StatusChip(label: meta.label, color: meta.color, icon: meta.icon),
                ],
              ),
              const SizedBox(height: HMSpace.sm),
              // 备忘录预览
              Container(
                padding: const EdgeInsets.all(HMSpace.sm),
                decoration: BoxDecoration(
                  color: color.surfaceContainerHighest.withValues(alpha: 0.4),
                  borderRadius: BorderRadius.circular(HMRadius.sm),
                ),
                child: Text(
                  _firstLine(coop.memoContent),
                  style: const TextStyle(fontSize: 12, height: 1.4),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(height: HMSpace.sm),
              Row(
                children: [
                  // 角色勾选：当前 user 身份用主色高亮 + "我"
                  if (iAmBuyer)
                    _RoleTag(
                      label: '我是买方',
                      active: true,
                      done: coop.buyerReviewed,
                    )
                  else
                    _RoleTag(
                      label: '买方',
                      active: false,
                      done: coop.buyerReviewed,
                    ),
                  const SizedBox(width: HMSpace.xs),
                  if (iAmSeller)
                    _RoleTag(
                      label: '我是卖方',
                      active: true,
                      done: coop.sellerReviewed,
                    )
                  else
                    _RoleTag(
                      label: '卖方',
                      active: false,
                      done: coop.sellerReviewed,
                    ),
                  const Spacer(),
                  // 按钮文案：基于"我"的真实评价状态
                  if (!isParticipant)
                    const Icon(Icons.chevron_right_rounded, size: 18)
                  else if (iHaveReviewed)
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: HMColors.success.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(HMRadius.full),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.check_circle, size: 12, color: HMColors.success),
                          SizedBox(width: 3),
                          Text(
                            '已评价',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: HMColors.success,
                            ),
                          ),
                        ],
                      ),
                    )
                  else
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: HMColors.warmGradient.colors.first
                            .withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(HMRadius.full),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.star_rounded,
                              size: 12, color: HMColors.statusPending),
                          const SizedBox(width: 3),
                          Text(
                            '去评价$opponentRole',
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: HMColors.statusPending,
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _firstLine(String memo) {
    final lines = memo.split('\n').where((l) => l.trim().isNotEmpty).toList();
    final contentIdx = lines.indexWhere((l) => l.contains('## 合作内容'));
    if (contentIdx >= 0 && contentIdx + 1 < lines.length) {
      return lines[contentIdx + 1];
    }
    return lines.isNotEmpty ? lines.first : '合作详情';
  }
}

/// 角色标签：active=true 表示"我是 xxx"（用主色高亮），done 表示该角色是否已评价
class _RoleTag extends StatelessWidget {
  final String label;
  final bool active;
  final bool done;
  const _RoleTag({
    required this.label,
    required this.active,
    required this.done,
  });

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final Color textColor;
    final Color bgColor;
    IconData icon;
    if (active) {
      // 当前用户身份：主色高亮
      textColor = color.primary;
      bgColor = color.primary.withValues(alpha: 0.1);
      icon = done ? Icons.check_circle : Icons.person_pin_rounded;
    } else {
      // 对方：灰色
      textColor = color.onSurface.withValues(alpha: 0.5);
      bgColor = color.surfaceContainerHighest.withValues(alpha: 0.4);
      icon = done ? Icons.check_circle : Icons.radio_button_unchecked;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(HMRadius.full),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: textColor),
          const SizedBox(width: 3),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: textColor,
              fontWeight: active ? FontWeight.w700 : FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================
//  邀请卡片
// ============================================================

class _InvitationCard extends ConsumerWidget {
  final Invitation inv;
  final bool isOutgoing; // 我发出的 = true / 我收到的 = false
  const _InvitationCard({required this.inv, required this.isOutgoing});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = Theme.of(context).colorScheme;
    final meta = invitationStatusMeta(inv.status);
    // 我发出的：显示"卖方"（对方）；我收到的：显示"买方"（对方）
    final counterpartyRole = isOutgoing ? '卖方' : '买方';
    final counterpartyRoleColor =
        isOutgoing ? HMColors.statusHandshaked : color.primary;
    final counterpartyId = isOutgoing ? inv.sellerId : inv.buyerId;

    return Card(
      child: InkWell(
        onTap: () => context.push('/invitations/${inv.id}'),
        borderRadius: BorderRadius.circular(HMRadius.lg),
        child: Padding(
          padding: const EdgeInsets.all(HMSpace.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 头部：图标 + 状态 + 编号
              Row(
                children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(
                      color: meta.color.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(HMRadius.sm),
                    ),
                    child: Icon(
                      isOutgoing ? Icons.send_rounded : Icons.inbox_rounded,
                      color: meta.color,
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: HMSpace.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '邀请 #${inv.id}',
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w600,
                            fontFeatures: [FontFeature.tabularFigures()],
                          ),
                        ),
                        const SizedBox(height: 2),
                        // 倒计时（如果有）
                        if (inv.status == 'pending' ||
                            inv.status == 'accepted')
                          InvitationCountdown(
                            deadline: inv.proposalDeadline ?? inv.expiredAt,
                          )
                        else
                          Text(
                            DateFormat('MM-dd HH:mm').format(inv.createdAt.toLocal()),
                            style: TextStyle(
                              fontSize: 11,
                              color: color.onSurface.withValues(alpha: 0.5),
                            ),
                          ),
                      ],
                    ),
                  ),
                  StatusChip(label: meta.label, color: meta.color, icon: meta.icon),
                ],
              ),
              const SizedBox(height: HMSpace.sm),
              // 需求摘要 + 卖方/买方 真实名 + 信用
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  DemandSummary(demandId: inv.demandId),
                  const SizedBox(height: 2),
                  UserSummary(
                    userId: counterpartyId,
                    role: counterpartyRole,
                    roleColor: counterpartyRoleColor,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ============================================================
//  历史（可折叠）
// ============================================================

// ============================================================
//  历史（可折叠）
// ============================================================

class _ArchiveSection extends StatefulWidget {
  final List<Cooperation> coops;
  const _ArchiveSection({required this.coops});

  @override
  State<_ArchiveSection> createState() => _ArchiveSectionState();
}

class _ArchiveSectionState extends State<_ArchiveSection> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: () => setState(() => _expanded = !_expanded),
          borderRadius: BorderRadius.circular(HMRadius.sm),
          child: Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: HMSpace.md + 2,
              vertical: HMSpace.sm,
            ),
            child: Row(
              children: [
                Icon(Icons.history_rounded,
                    size: 16, color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6)),
                const SizedBox(width: 6),
                Text(
                  '历史合作',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                  ),
                ),
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(HMRadius.full),
                  ),
                  child: Text(
                    '${widget.coops.length}',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const Spacer(),
                Icon(
                  _expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                  color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ],
            ),
          ),
        ),
        if (_expanded)
          Padding(
            padding: const EdgeInsets.fromLTRB(
                HMSpace.md, 0, HMSpace.md, 0),
            child: Column(
              children: widget.coops
                  .map((c) => Padding(
                        padding: const EdgeInsets.only(bottom: HMSpace.xs),
                        child: _CooperationCard(coop: c),
                      ))
                  .toList(),
            ),
          ),
      ],
    );
  }
}

// ============================================================
//  空状态
// ============================================================

class _EmptyDashboard extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return FutureBuilder<_UserRole>(
      future: _detectRole(ref),
      builder: (context, snap) {
        final role = snap.data ?? _UserRole.unknown;
        final (icon, title, subtitle, btnLabel, btnIcon, btnRoute) = switch (role) {
          _UserRole.buyer => (
            Icons.handshake_outlined,
            '还没有合作',
            '走完"需求 → 邀请 → 接单 → 方案 → 握手"后，\n合作会出现在这里',
            '去发布需求',
            Icons.search_rounded,
            '/demands',
          ),
          _UserRole.seller => (
            Icons.handshake_outlined,
            '还没有合作',
            '走完"接单 → 提交方案 → 买方确认"后，\n合作会出现在这里',
            '查看我的邀请',
            Icons.inbox_rounded,
            '/invitations',
          ),
          _UserRole.both => (
            Icons.handshake_outlined,
            '还没有合作',
            '走完撮合流程后，\n合作会出现在这里',
            '去发需求',
            Icons.search_rounded,
            '/demands',
          ),
          _ => (
            Icons.handshake_outlined,
            '还没有合作',
            '先发布需求或房源开始撮合吧',
            '去发布房源',
            Icons.add_home_work_rounded,
            '/properties/new',
          ),
        };
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: HMSpace.md),
          child: EmptyState(
            icon: icon,
            title: title,
            subtitle: subtitle,
            action: FilledButton.icon(
              onPressed: () => context.go(btnRoute),
              icon: Icon(btnIcon, size: 18),
              label: Text(btnLabel),
            ),
          ),
        );
      },
    );
  }
}

// ============================================================
//  加载中
// ============================================================

class _LoadingState extends StatelessWidget {
  const _LoadingState();
  @override
  Widget build(BuildContext context) {
    return ListView(
      children: const [
        SizedBox(height: HMSpace.md),
        SkeletonListTile(),
        SkeletonListTile(),
        SkeletonListTile(),
        SkeletonListTile(),
      ],
    );
  }
}
