/// 合作详情 - 时间线 + 备忘录
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_tokens.dart';
import '../../core/widgets/status_chip.dart';
import 'cooperation_models.dart';
import '../auth/auth_state.dart';
import 'cooperation_service.dart';

final _coopProvider = FutureProvider.autoDispose.family<Cooperation, int>(
  (ref, id) {
    ref.watch(authProvider.select((a) => a.userId));
    return ref.read(cooperationServiceProvider).get(id);
  },
);

class CooperationDetailScreen extends ConsumerWidget {
  final int cooperationId;
  const CooperationDetailScreen({super.key, required this.cooperationId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_coopProvider(cooperationId));
    return Scaffold(
      appBar: AppBar(
        title: Text('COOP-$cooperationId'),
        leading: IconButton(
          tooltip: '返回合作首页',
          icon: const Icon(Icons.arrow_back_rounded),
          onPressed: () => context.go('/cooperations'),
        ),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () async {
              ref.invalidate(_coopProvider(cooperationId));
              try {
                await ref.read(_coopProvider(cooperationId).future);
              } catch (_) {}
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('已刷新'),
                    duration: Duration(seconds: 1),
                    behavior: SnackBarBehavior.floating,
                  ),
                );
              }
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.go('/cooperations'),
        icon: const Icon(Icons.dashboard_rounded, size: 18),
        label: const Text('返回合作首页'),
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('加载失败: $e')),
        data: (c) {
          final color = Theme.of(context).colorScheme;
          final meta = cooperationStatusMeta(c.status);
          return RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(_coopProvider(c.id));
              await ref.read(_coopProvider(c.id).future);
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
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
                  child: Row(
                    children: [
                      Container(
                        width: 56,
                        height: 56,
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.25),
                          borderRadius: BorderRadius.circular(HMRadius.md),
                        ),
                        child: Icon(meta.icon, color: Colors.white, size: 30),
                      ),
                      const SizedBox(width: HMSpace.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              meta.label,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 22,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '签订于 ${DateFormat('yyyy-MM-dd HH:mm').format(c.signedAt.toLocal())}',
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.9),
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: HMSpace.md),
                // 合作时间线
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(HMSpace.md),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.timeline_rounded,
                                size: 18, color: color.primary),
                            const SizedBox(width: 6),
                            const Text(
                              '合作进展',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: HMSpace.md),
                        _Timeline(
                          steps: [
                            _TimelineStep(
                              icon: Icons.send_rounded,
                              title: '发起邀请',
                              subtitle: '买方邀请卖方',
                              done: true,
                            ),
                            _TimelineStep(
                              icon: Icons.check_circle_outline,
                              title: '卖方接单',
                              subtitle: '24h 内响应',
                              done: true,
                            ),
                            _TimelineStep(
                              icon: Icons.description_outlined,
                              title: '提交方案',
                              subtitle: '2h 内完成',
                              done: true,
                            ),
                            _TimelineStep(
                              icon: Icons.handshake_rounded,
                              title: '握手达成',
                              subtitle: DateFormat('MM-dd HH:mm')
                                  .format(c.signedAt.toLocal()),
                              done: c.status != 'terminated',
                              highlight: c.status == 'handshaked',
                            ),
                            _TimelineStep(
                              icon: Icons.task_alt_rounded,
                              title: '合作完成',
                              subtitle: c.buyerReviewed && c.sellerReviewed
                                  ? '双方已互评'
                                  : '待双方评价',
                              done: c.buyerReviewed && c.sellerReviewed,
                              isLast: true,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: HMSpace.md),
                // 合作备忘录
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(HMSpace.md),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.assignment_rounded,
                                size: 18, color: color.primary),
                            const SizedBox(width: 6),
                            const Text(
                              '合作备忘录',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: HMSpace.sm),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(HMSpace.sm),
                          decoration: BoxDecoration(
                            color: color.surfaceContainerHighest.withValues(alpha: 0.4),
                            borderRadius: BorderRadius.circular(HMRadius.sm),
                          ),
                          child: SelectableText(
                            c.memoContent,
                            style: const TextStyle(
                              fontSize: 13,
                              height: 1.6,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: HMSpace.md),
                // 合作评价（只展示当前用户角色对应的评价对方按钮 + 评价内容）
                Builder(
                  builder: (_) {
                    final myId = ref.read(authProvider).userId;
                    final iAmBuyer = myId == c.buyerId;
                    final iAmSeller = myId == c.sellerId;
                    final isParticipant = iAmBuyer || iAmSeller;
                    // 当前用户评价哪一方
                    final opponentRole = iAmBuyer ? '卖方' : (iAmSeller ? '买方' : '对方');
                    // 当前用户是否已评
                    final iHaveReviewed = iAmBuyer
                        ? c.buyerReviewed
                        : (iAmSeller ? c.sellerReviewed : true);
                    // 能否评价（参与方 + 握手状态 + 自己未评）
                    final iCanReview = isParticipant &&
                        c.status == 'handshaked' &&
                        !iHaveReviewed;

                    if (!isParticipant) {
                      // 非参与方：只读
                      return Card(
                        child: Padding(
                          padding: const EdgeInsets.all(HMSpace.md),
                          child: Row(
                            children: [
                              Icon(Icons.star_rate_rounded,
                                  size: 18, color: color.onSurface.withValues(alpha: 0.4)),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  '你不在此合作中，仅可查看',
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: color.onSurface.withValues(alpha: 0.5),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    }

                    // 参与方：只展示「我作为 X 评价 Y」一栏
                    return Card(
                      child: Padding(
                        padding: const EdgeInsets.all(HMSpace.md),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(Icons.star_rate_rounded,
                                    size: 18, color: color.primary),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: Text(
                                    '我作为${iAmBuyer ? "买方" : "卖方"}评价$opponentRole',
                                    style: const TextStyle(
                                      fontSize: 15,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                                Text(
                                  iHaveReviewed ? '已评价' : '待评价',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: iHaveReviewed
                                        ? HMColors.success
                                        : HMColors.statusPending,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                            // 已评价：提示
                            if (iHaveReviewed) ...[
                              const SizedBox(height: HMSpace.sm),
                              Container(
                                padding: const EdgeInsets.all(HMSpace.sm),
                                decoration: BoxDecoration(
                                  color: HMColors.success.withValues(alpha: 0.08),
                                  borderRadius: BorderRadius.circular(HMRadius.sm),
                                ),
                                child: Row(
                                  children: [
                                    const Icon(Icons.check_circle,
                                        size: 16, color: HMColors.success),
                                    const SizedBox(width: 6),
                                    Expanded(
                                      child: Text(
                                        '你已记录对此次合作的评价',
                                        style: TextStyle(
                                          fontSize: 13,
                                          color: color.onSurface.withValues(alpha: 0.7),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                            // 未评价：展示「评价 $opponentRole」按钮
                            if (iCanReview) ...[
                              const SizedBox(height: HMSpace.md),
                              SizedBox(
                                width: double.infinity,
                                child: FilledButton.icon(
                                  onPressed: () => context.push(
                                      '/cooperations/${c.id}/review'),
                                  icon: const Icon(Icons.star_rounded),
                                  label: Text('评价$opponentRole'),
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                    );
                  },
                ),
                const SizedBox(height: HMSpace.md),
                // （"返回合作首页" 移到了右下角 FloatingActionButton）
                const SizedBox(height: 96),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _TimelineStep {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool done;
  final bool highlight;
  final bool isLast;
  _TimelineStep({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.done = false,
    this.highlight = false,
    this.isLast = false,
  });
}

class _Timeline extends StatelessWidget {
  final List<_TimelineStep> steps;
  const _Timeline({required this.steps});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    return Column(
      children: [
        for (int i = 0; i < steps.length; i++) ...[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 圆点 + 竖线
              Column(
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: steps[i].done
                          ? (steps[i].highlight
                              ? HMColors.statusHandshaked
                              : color.primary)
                          : color.surfaceContainerHighest,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      steps[i].done ? steps[i].icon : Icons.circle_outlined,
                      color: steps[i].done
                          ? Colors.white
                          : color.onSurface.withValues(alpha: 0.3),
                      size: 16,
                    ),
                  ),
                  if (!steps[i].isLast)
                    Container(
                      width: 2,
                      height: 32,
                      color: steps[i + 1].done || steps[i].done
                          ? color.primary.withValues(alpha: 0.4)
                          : color.surfaceContainerHighest,
                    ),
                ],
              ),
              const SizedBox(width: HMSpace.sm),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(top: 4, bottom: HMSpace.sm),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        steps[i].title,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: steps[i].done
                              ? color.onSurface
                              : color.onSurface.withValues(alpha: 0.4),
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        steps[i].subtitle,
                        style: TextStyle(
                          fontSize: 12,
                          color: color.onSurface.withValues(alpha: 0.6),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

