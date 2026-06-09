/// 需求列表（买方视角）- 卡片式设计
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_tokens.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/status_chip.dart';
import '../auth/auth_state.dart';
import 'demand_models.dart';
import 'demand_service.dart';

final _myDemandsProvider = FutureProvider.autoDispose<List<Demand>>((ref) async {
  ref.watch(authProvider.select((a) => a.userId));
  return ref.read(demandServiceProvider).listMyDemands();
});

class DemandListScreen extends ConsumerWidget {
  const DemandListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncDemands = ref.watch(_myDemandsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('我的需求'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(_myDemandsProvider),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/demands/new').then((_) {
              ref.invalidate(_myDemandsProvider);
            }),
        icon: const Icon(Icons.add_rounded),
        label: const Text('发布需求'),
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(_myDemandsProvider);
          await ref.read(_myDemandsProvider.future);
        },
        child: asyncDemands.when(
          loading: () => ListView(
            children: const [
              SizedBox(height: HMSpace.md),
              SkeletonListTile(),
              SkeletonListTile(),
              SkeletonListTile(),
            ],
          ),
          error: (e, _) => ErrorState(
            message: '$e',
            onRetry: () => ref.invalidate(_myDemandsProvider),
          ),
          data: (demands) {
            if (demands.isEmpty) {
              return const _EmptyDemands();
            }
            return ListView.separated(
              padding: const EdgeInsets.fromLTRB(
                HMSpace.md,
                HMSpace.md,
                HMSpace.md,
                96,
              ),
              itemCount: demands.length,
              separatorBuilder: (_, __) => const SizedBox(height: HMSpace.sm),
              itemBuilder: (_, i) => _DemandCard(
                demand: demands[i],
                onTap: () => context.push('/demands/${demands[i].id}/recommendations'),
                onClose: () => _confirmClose(context, ref, demands[i]),
              ),
            );
          },
        ),
      ),
    );
  }

  /// 二次确认后下架需求
  Future<void> _confirmClose(
    BuildContext context,
    WidgetRef ref,
    Demand demand,
  ) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        icon: const Icon(Icons.delete_outline_rounded, size: 32),
        title: const Text('下架需求？'),
        content: Text(
          '「${demand.district} ${(demand.priceMin / 10000).toStringAsFixed(0)}-${(demand.priceMax / 10000).toStringAsFixed(0)}万」\n\n'
          '下架后：\n'
          '• 买家端不再展示\n'
          '• 不会推荐给新卖家\n'
          '• 已发邀请可以继续处理',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('取消'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('确认下架'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ref.read(demandServiceProvider).closeDemand(demand.id);
      ref.invalidate(_myDemandsProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('需求已下架'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('下架失败: $e')),
        );
      }
    }
  }
}

class _EmptyDemands extends StatelessWidget {
  const _EmptyDemands();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        SizedBox(
          height: MediaQuery.of(context).size.height * 0.6,
          child: const EmptyState(
            icon: Icons.search_off_rounded,
            title: '还没有发布过需求',
            subtitle: '点击下方"发布需求"按钮，让 AI 帮你匹配同行',
          ),
        ),
      ],
    );
  }
}

class _DemandCard extends StatelessWidget {
  final Demand demand;
  final VoidCallback onTap;
  final VoidCallback? onClose;
  const _DemandCard({required this.demand, required this.onTap, this.onClose});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final priceMinWan = (demand.priceMin / 10000).toStringAsFixed(0);
    final priceMaxWan = (demand.priceMax / 10000).toStringAsFixed(0);
    final meta = demandStatusMeta(demand.status);
    final fmt = DateFormat('MM-dd HH:mm');
    final canClose = demand.status == 'active' || demand.status == 'matched';

    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(HMRadius.lg),
        child: Padding(
          padding: const EdgeInsets.all(HMSpace.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 头部：区域 + 状态
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: color.primaryContainer.withValues(alpha: 0.6),
                      borderRadius: BorderRadius.circular(HMRadius.sm),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.location_on_rounded, size: 14, color: color.onPrimaryContainer),
                        const SizedBox(width: 2),
                        Text(
                          demand.district,
                          style: TextStyle(
                            color: color.onPrimaryContainer,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                  StatusChip(label: meta.label, color: meta.color, icon: meta.icon),
                ],
              ),
              const SizedBox(height: HMSpace.sm),
              // 价格主信息（大字）
              Row(
                crossAxisAlignment: CrossAxisAlignment.baseline,
                textBaseline: TextBaseline.alphabetic,
                children: [
                  Text(
                    '$priceMinWan',
                    style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                          color: color.primary,
                          fontWeight: FontWeight.w700,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: Text(
                      '~',
                      style: TextStyle(
                        color: color.onSurface.withValues(alpha: 0.5),
                        fontSize: 18,
                      ),
                    ),
                  ),
                  Text(
                    '$priceMaxWan',
                    style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                          color: color.primary,
                          fontWeight: FontWeight.w700,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    '万',
                    style: TextStyle(
                      color: color.onSurface.withValues(alpha: 0.7),
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: HMSpace.sm),
              // 户型 + 时间
              Wrap(
                spacing: HMSpace.md,
                runSpacing: HMSpace.xs,
                children: [
                  _MetaChip(icon: Icons.bedroom_parent_rounded, text: demand.layouts.join(' / '), iconColor: color.onSurface.withValues(alpha: 0.6)),
                  _MetaChip(icon: Icons.access_time_rounded, text: demand.viewingTime.join(' / '), iconColor: color.onSurface.withValues(alpha: 0.6)),
                  if (demand.qualification != '不限')
                    _MetaChip(icon: Icons.verified_user_outlined, text: demand.qualification, iconColor: color.onSurface.withValues(alpha: 0.6)),
                ],
              ),
              const SizedBox(height: HMSpace.sm),
              // 底部时间 + AI 推荐入口
              Row(
                children: [
                  Icon(
                    Icons.schedule,
                    size: 12,
                    color: color.onSurface.withValues(alpha: 0.4),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    fmt.format(demand.createdAt),
                    style: TextStyle(
                      fontSize: 11,
                      color: color.onSurface.withValues(alpha: 0.4),
                    ),
                  ),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      gradient: HMColors.primaryGradient,
                      borderRadius: BorderRadius.circular(HMRadius.full),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.auto_awesome, size: 12, color: Colors.white),
                        SizedBox(width: 4),
                        Text(
                          '查看推荐',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (canClose && onClose != null) ...[
                    const SizedBox(width: 4),
                    IconButton(
                      icon: const Icon(Icons.more_horiz_rounded, size: 20),
                      onPressed: () => _showCardMenu(context),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                      tooltip: '更多操作',
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// 显示卡片菜单（下架等）
  void _showCardMenu(BuildContext context) async {
    if (onClose == null) return;
    final color = Theme.of(context).colorScheme;
    final action = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: BoxDecoration(
          color: color.surface,
          borderRadius: const BorderRadius.vertical(
            top: Radius.circular(HMRadius.xl),
          ),
        ),
        padding: const EdgeInsets.symmetric(vertical: HMSpace.sm),
        child: SafeArea(
          top: false,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: Icon(Icons.delete_outline_rounded,
                    color: color.error),
                title: Text(
                  '下架需求',
                  style: TextStyle(color: color.error, fontWeight: FontWeight.w600),
                ),
                subtitle: const Text('下架后买家端不可见，邀请会停止匹配',
                    style: TextStyle(fontSize: 11)),
                onTap: () => Navigator.of(ctx).pop('close'),
              ),
              ListTile(
                leading: const Icon(Icons.close_rounded),
                title: const Text('取消'),
                onTap: () => Navigator.of(ctx).pop(),
              ),
            ],
          ),
        ),
      ),
    );
    if (action == 'close' && onClose != null) {
      onClose!();
    }
  }
}

class _MetaChip extends StatelessWidget {
  final IconData icon;
  final String text;
  final Color iconColor;
  const _MetaChip({required this.icon, required this.text, required this.iconColor});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: iconColor),
        const SizedBox(width: 4),
        Text(
          text,
          style: const TextStyle(fontSize: 12, color: Color(0xFF49454F)),
        ),
      ],
    );
  }
}
