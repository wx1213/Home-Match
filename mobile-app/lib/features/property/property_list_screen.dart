/// 我的房源 - 卡片式设计
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_tokens.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/status_chip.dart';
import '../auth/auth_state.dart';
import 'property_models.dart';
import 'property_service.dart';

final _myPropertiesProvider =
    FutureProvider.autoDispose<List<Property>>((ref) async {
  ref.watch(authProvider.select((a) => a.userId));
  return ref.read(propertyServiceProvider).listMyProperties();
});

class PropertyListScreen extends ConsumerWidget {
  const PropertyListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncProps = ref.watch(_myPropertiesProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('我的房源'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(_myPropertiesProvider),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/properties/new').then((_) {
          ref.invalidate(_myPropertiesProvider);
        }),
        icon: const Icon(Icons.add),
        label: const Text('发布房源'),
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(_myPropertiesProvider),
        child: asyncProps.when(
          loading: () => ListView(
            padding: EdgeInsets.zero,
            children: const [
              SizedBox(height: HMSpace.md),
              SkeletonListTile(),
              SkeletonListTile(),
              SkeletonListTile(),
            ],
          ),
          error: (e, _) => ErrorState(
            message: '$e',
            onRetry: () => ref.invalidate(_myPropertiesProvider),
          ),
          data: (props) {
            if (props.isEmpty) {
              return const _EmptyProperties();
            }
            return ListView.builder(
              padding: const EdgeInsets.only(bottom: 96),
              itemCount: props.length,
              itemBuilder: (_, i) => _PropertyCard(
                property: props[i],
                onTap: () => context.push('/properties/${props[i].id}'),
                onClose: () => _confirmDelist(context, ref, props[i]),
              ),
            );
          },
        ),
      ),
    );
  }

  /// 二次确认后下架房源
  Future<void> _confirmDelist(
    BuildContext context,
    WidgetRef ref,
    Property property,
  ) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        icon: const Icon(Icons.delete_outline_rounded, size: 32),
        title: const Text('下架房源？'),
        content: Text(
          '「${property.community} ${property.layout}」\n\n'
          '下架后：\n'
          '• 买家端不再展示\n'
          '• 不会被推荐给买方\n'
          '• 历史合作 / 评价不受影响',
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
      await ref.read(propertyServiceProvider).delistProperty(property.id);
      ref.invalidate(_myPropertiesProvider);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('房源已下架'),
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

class _EmptyProperties extends StatelessWidget {
  const _EmptyProperties();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      children: [
        SizedBox(
          height: MediaQuery.of(context).size.height * 0.6,
          child: const EmptyState(
            icon: Icons.home_outlined,
            title: '还没有房源',
            subtitle: '发布你的第一套房源，开始接合作邀请',
          ),
        ),
      ],
    );
  }
}

class _PropertyCard extends StatelessWidget {
  final Property property;
  final VoidCallback onTap;
  final VoidCallback? onClose;
  const _PropertyCard({
    required this.property,
    required this.onTap,
    this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final priceWan = (property.totalPrice / 10000).toStringAsFixed(0);
    final meta = propertyStatusMeta(property.status);
    final canClose = onClose != null && property.status == 'active';

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: HMSpace.md, vertical: HMSpace.xs),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(HMRadius.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 顶部图 + 状态徽章
            Stack(
              children: [
                // 图片占位
                Container(
                  height: 140,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        color.primary.withValues(alpha: 0.4),
                        color.primary.withValues(alpha: 0.15),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(HMRadius.lg),
                    ),
                  ),
                  child: Center(
                    child: Icon(
                      Icons.home_rounded,
                      size: 56,
                      color: Colors.white.withValues(alpha: 0.7),
                    ),
                  ),
                ),
                // 状态徽章
                Positioned(
                  top: HMSpace.xs,
                  right: HMSpace.xs,
                  child: StatusChip(
                    label: meta.label,
                    color: meta.color,
                    icon: meta.icon,
                    filled: true,
                  ),
                ),
                // 实勘徽章
                if (property.isVerified)
                  Positioned(
                    top: HMSpace.xs,
                    left: HMSpace.xs,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.5),
                        borderRadius: BorderRadius.circular(HMRadius.full),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.verified_rounded, size: 12, color: Colors.white),
                          SizedBox(width: 4),
                          Text(
                            '已实勘',
                            style: TextStyle(color: Colors.white, fontSize: 10),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),

            // 信息
            Padding(
              padding: const EdgeInsets.all(HMSpace.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 价格 + 更多按钮
                  Row(
                    children: [
                      Text(
                        priceWan,
                        style: TextStyle(
                          color: color.primary,
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.only(left: 2, bottom: 2),
                        child: Text(
                          '万',
                          style: TextStyle(
                            color: color.onSurface.withValues(alpha: 0.6),
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      const Spacer(),
                      if (canClose)
                        IconButton(
                          icon: Icon(
                            Icons.more_vert_rounded,
                            color: color.onSurface.withValues(alpha: 0.4),
                            size: 20,
                          ),
                          onPressed: onClose,
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                          tooltip: '下架',
                        ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      _MetaChip(
                        icon: Icons.bedroom_parent_rounded,
                        text: property.layout,
                        iconColor: color.onSurface.withValues(alpha: 0.6),
                        iconSize: 13,
                      ),
                      const SizedBox(width: HMSpace.md),
                      _MetaChip(
                        icon: Icons.square_foot_rounded,
                        text: '${property.area.toStringAsFixed(0)}㎡',
                        iconColor: color.onSurface.withValues(alpha: 0.6),
                        iconSize: 13,
                      ),
                      const SizedBox(width: HMSpace.md),
                      _MetaChip(
                        icon: Icons.access_time_rounded,
                        text: property.viewingTime,
                        iconColor: color.onSurface.withValues(alpha: 0.6),
                        iconSize: 13,
                      ),
                    ],
                  ),
                  if (property.tags.isNotEmpty) ...[
                    const SizedBox(height: HMSpace.sm),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: property.tags
                          .take(3)
                          .map((t) => HMTag(label: t, color: color.primary))
                          .toList(),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  final IconData icon;
  final String text;
  final Color iconColor;
  final double iconSize;
  const _MetaChip({
    required this.icon,
    required this.text,
    required this.iconColor,
    this.iconSize = 14,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: iconSize, color: iconColor),
        const SizedBox(width: 4),
        Text(
          text,
          style: TextStyle(
            fontSize: 12,
            color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.7),
          ),
        ),
      ],
    );
  }
}
