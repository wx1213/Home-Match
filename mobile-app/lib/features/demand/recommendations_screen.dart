/// 推荐卖方 - Top 5 列表 (卡片式 + 等级徽章)
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_tokens.dart';
import '../../core/widgets/credit_badge.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/status_chip.dart';
import 'demand_models.dart';
import 'demand_service.dart';

final _recommendationsProvider =
    FutureProvider.family<List<SellerRecommendation>, int>((ref, demandId) async {
  return ref.read(demandServiceProvider).getRecommendations(demandId);
});

class RecommendationsScreen extends ConsumerWidget {
  final int demandId;
  const RecommendationsScreen({super.key, required this.demandId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncRecs = ref.watch(_recommendationsProvider(demandId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI 推荐'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(_recommendationsProvider(demandId)),
          ),
          PopupMenuButton<String>(
            tooltip: '更多',
            icon: const Icon(Icons.more_vert_rounded),
            onSelected: (v) {
              if (v == 'close') {
                _confirmClose(context, ref, demandId);
              }
            },
            itemBuilder: (_) => const [
              PopupMenuItem<String>(
                value: 'close',
                child: Row(
                  children: [
                    Icon(Icons.delete_outline_rounded,
                        color: Colors.red, size: 20),
                    SizedBox(width: 8),
                    Text('下架需求'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: asyncRecs.when(
        loading: () => ListView(
          children: const [
            SizedBox(height: HMSpace.md),
            SkeletonListTile(),
            SkeletonListTile(),
            SkeletonListTile(),
            SkeletonListTile(),
            SkeletonListTile(),
          ],
        ),
        error: (e, _) => ErrorState(
          message: '$e',
          onRetry: () => ref.invalidate(_recommendationsProvider(demandId)),
        ),
        data: (recs) {
          if (recs.isEmpty) {
            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                SizedBox(
                  height: MediaQuery.of(context).size.height * 0.6,
                  child: const EmptyState(
                    icon: Icons.search_off_rounded,
                    title: '暂无推荐',
                    subtitle: '暂时没有合适的同行，过会再来看看',
                  ),
                ),
              ],
            );
          }
          return CustomScrollView(
            slivers: [
              SliverToBoxAdapter(
                child: Container(
                  margin: const EdgeInsets.fromLTRB(
                    HMSpace.md,
                    HMSpace.md,
                    HMSpace.md,
                    0,
                  ),
                  padding: const EdgeInsets.all(HMSpace.md),
                  decoration: BoxDecoration(
                    gradient: HMColors.primaryGradient,
                    borderRadius: BorderRadius.circular(HMRadius.lg),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.auto_awesome, color: Colors.white, size: 22),
                      const SizedBox(width: HMSpace.xs),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'AI 智能匹配',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '基于区域/价格/户型/时间/信用综合排序',
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.85),
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(HMRadius.full),
                        ),
                        child: Text(
                          'Top ${recs.length}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(
                  HMSpace.md,
                  HMSpace.sm,
                  HMSpace.md,
                  HMSpace.lg,
                ),
                sliver: SliverList.separated(
                  itemCount: recs.length,
                  separatorBuilder: (_, __) => const SizedBox(height: HMSpace.sm),
                  itemBuilder: (_, i) => _SellerCard(rec: recs[i], demandId: demandId),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  /// 二次确认后下架需求（推荐页入口）
  Future<void> _confirmClose(
    BuildContext context,
    WidgetRef ref,
    int demandId,
  ) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        icon: const Icon(Icons.delete_outline_rounded, size: 32),
        title: const Text('下架需求？'),
        content: const Text(
          '下架后：\n'
          '• 对其他经纪人隐藏\n'
          '• 不再推荐给新同行\n'
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
      await ref.read(demandServiceProvider).closeDemand(demandId);
      // 清理本地缓存的推荐结果（这个 demand 不再有效）
      ref.invalidate(_recommendationsProvider(demandId));
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('需求已下架'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      // 用 go 强制回到需求列表根路由，避免深链进来时 pop 出错
      context.go('/demands');
    } on DioException catch (e) {
      if (!context.mounted) return;
      final msg = e.response?.data is Map
          ? (e.response?.data['message']?.toString() ?? e.message ?? '网络错误')
          : (e.message ?? '网络错误');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('下架失败: $msg'), behavior: SnackBarBehavior.floating),
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('下架失败: $e'), behavior: SnackBarBehavior.floating),
      );
    }
  }
}

class _SellerCard extends ConsumerWidget {
  final SellerRecommendation rec;
  final int demandId;
  const _SellerCard({required this.rec, required this.demandId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = Theme.of(context).colorScheme;
    final seller = rec.seller;
    final properties = rec.matchedProperties;
    final sellerName = seller['display_name'] as String? ?? '用户';
    final credit = (seller['credit_score'] as num?)?.toDouble() ?? 60;
    final matchPct = (rec.matchScore * 100).toStringAsFixed(0);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(HMSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 头部：排名 + 头像 + 姓名 + 信用
            Row(
              children: [
                // 排名徽章
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    gradient: rec.rank <= 3 ? HMColors.warmGradient : null,
                    color: rec.rank > 3 ? color.surfaceContainerHighest : null,
                    borderRadius: BorderRadius.circular(HMRadius.sm),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    '#${rec.rank}',
                    style: TextStyle(
                      color: rec.rank <= 3 ? Colors.white : color.onSurface,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    ),
                  ),
                ),
                const SizedBox(width: HMSpace.sm),
                HMUserAvatar(name: sellerName, size: 44),
                const SizedBox(width: HMSpace.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              sellerName,
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 16,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 4),
                          Icon(
                            Icons.verified_rounded,
                            size: 14,
                            color: HMColors.creditBlue,
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      CreditBadge(score: credit, compact: true),
                    ],
                  ),
                ),
                // 匹配度
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    ShaderMask(
                      shaderCallback: (rect) => HMColors.primaryGradient.createShader(rect),
                      child: Text(
                        '$matchPct%',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                          fontFeatures: [FontFeature.tabularFigures()],
                        ),
                      ),
                    ),
                    Text(
                      '匹配度',
                      style: TextStyle(
                        fontSize: 10,
                        color: color.onSurface.withValues(alpha: 0.5),
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: HMSpace.sm),
            const Divider(height: 1),
            const SizedBox(height: HMSpace.sm),
            // 匹配房源
            if (properties.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: HMSpace.xs),
                child: Text(
                  '该经纪人暂无匹配房源',
                  style: TextStyle(
                    fontSize: 12,
                    color: color.onSurface.withValues(alpha: 0.5),
                  ),
                ),
              )
            else
              ...properties.take(2).map((p) => _PropertyRow(property: p)),
            const SizedBox(height: HMSpace.sm),
            // 操作按钮
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(40),
                    ),
                    onPressed: () => _showSellerDetail(context, seller, properties),
                    child: const Text('查看详情', style: TextStyle(fontSize: 13)),
                  ),
                ),
                const SizedBox(width: HMSpace.xs),
                Expanded(
                  child: FilledButton.icon(
                    style: FilledButton.styleFrom(
                      minimumSize: const Size.fromHeight(40),
                    ),
                    onPressed: () => _sendInvitation(context, ref, seller),
                    icon: const Icon(Icons.send_rounded, size: 16),
                    label: const Text('邀请合作', style: TextStyle(fontSize: 13)),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// 显示卖家详情：完整的名片 + 所有匹配到的房源
  void _showSellerDetail(
    BuildContext context,
    Map<String, dynamic> seller,
    List<Map<String, dynamic>> properties,
  ) {
    final color = Theme.of(context).colorScheme;
    final sellerName = seller['display_name'] as String? ??
        seller['name'] as String? ??
        '用户';
    final credit = (seller['credit_score'] as num?)?.toDouble() ?? 60;
    final rating = (seller['rating_avg'] as num?)?.toDouble() ?? 0;
    final ratingCount = (seller['rating_count'] as num?)?.toInt() ?? 0;
    final isVerified = seller['is_verified'] as bool? ?? false;
    final completed = (seller['completed_count'] as num?)?.toInt() ?? 0;

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetCtx) {
        return Container(
          decoration: BoxDecoration(
            color: color.surface,
            borderRadius: const BorderRadius.vertical(
              top: Radius.circular(HMRadius.xl),
            ),
          ),
          padding: const EdgeInsets.fromLTRB(
            HMSpace.md,
            HMSpace.sm,
            HMSpace.md,
            HMSpace.lg,
          ),
          child: SafeArea(
            top: false,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 顶部滑条
                  Center(
                    child: Container(
                      width: 36,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: HMSpace.md),
                      decoration: BoxDecoration(
                        color: color.onSurface.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  // 卖家名片
                  Row(
                    children: [
                      HMUserAvatar(name: sellerName, size: 56),
                      const SizedBox(width: HMSpace.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Flexible(
                                  child: Text(
                                    sellerName,
                                    style: const TextStyle(
                                      fontSize: 18,
                                      fontWeight: FontWeight.w700,
                                    ),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                if (isVerified) ...[
                                  const SizedBox(width: 4),
                                  const Icon(
                                    Icons.verified_rounded,
                                    size: 16,
                                    color: HMColors.success,
                                  ),
                                ],
                              ],
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '用户 #${seller['id']} · 已完成 $completed 单合作',
                              style: TextStyle(
                                fontSize: 12,
                                color: color.onSurface.withValues(alpha: 0.6),
                              ),
                            ),
                            const SizedBox(height: HMSpace.xs),
                            CreditBadge(score: credit),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: HMSpace.md),
                  // 数据条
                  Row(
                    children: [
                      _Stat(
                        label: '评价均分',
                        value: ratingCount > 0
                            ? '${rating.toStringAsFixed(1)} 星'
                            : '暂无',
                        color: color.primary,
                      ),
                      const _StatDivider(),
                      _Stat(
                        label: '评价数',
                        value: '$ratingCount',
                        color: color.primary,
                      ),
                      const _StatDivider(),
                      _Stat(
                        label: '已实勘',
                        value: isVerified ? '✓ 是' : '✗ 否',
                        color: isVerified ? HMColors.success : HMColors.statusExpired,
                      ),
                    ],
                  ),
                  const SizedBox(height: HMSpace.md),
                  // 匹配的房源列表
                  Row(
                    children: [
                      Icon(Icons.home_work_rounded, size: 16, color: color.primary),
                      const SizedBox(width: 6),
                      Text(
                        '匹配房源（${properties.length}）',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: HMSpace.xs),
                  if (properties.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: HMSpace.md),
                      child: Text(
                        '暂无可展示的房源',
                        style: TextStyle(
                          fontSize: 12,
                          color: color.onSurface.withValues(alpha: 0.5),
                        ),
                      ),
                    )
                  else
                    ...properties.map(
                      (p) => Padding(
                        padding: const EdgeInsets.only(bottom: HMSpace.xs),
                        child: _DetailPropertyTile(
                          property: p,
                          onTap: () {
                            // 跳到该房源详情
                            Navigator.of(sheetCtx).pop();
                            final pid = p['id'] as int?;
                            if (pid != null) {
                              context.push('/properties/$pid');
                            }
                          },
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Future<void> _sendInvitation(
    BuildContext context,
    WidgetRef ref,
    Map<String, dynamic> seller,
  ) async {
    try {
      await ref.read(demandServiceProvider).runInvitation(
            demandId: demandId,
            sellerId: seller['id'] as int,
          );
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('邀请已发送！24h 内未响应自动失效'),
            behavior: SnackBarBehavior.floating,
          ),
        );
        context.go('/invitations');
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('发送失败: $e'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }
}

class _PropertyRow extends StatelessWidget {
  final Map<String, dynamic> property;
  const _PropertyRow({required this.property});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final priceWan = ((property['total_price'] as num) / 10000).toStringAsFixed(0);
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: color.surfaceContainerHighest.withValues(alpha: 0.4),
          borderRadius: BorderRadius.circular(HMRadius.sm),
        ),
        child: Row(
          children: [
            Icon(Icons.home_outlined, size: 16, color: color.onSurface.withValues(alpha: 0.6)),
            const SizedBox(width: 6),
            Expanded(
              child: Text(
                '${property['community']} · ${property['layout']} · ${property['area']}㎡',
                style: const TextStyle(fontSize: 13),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: 6),
            Text(
              '$priceWan万',
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
            ),
          ],
        ),
      ),
    );
  }
}

// ============================================================
//  "查看详情" 弹窗用的辅助组件
// ============================================================

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _Stat({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 16,
              fontWeight: FontWeight.w700,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatDivider extends StatelessWidget {
  const _StatDivider();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 0.5,
      height: 24,
      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.2),
      margin: const EdgeInsets.symmetric(horizontal: HMSpace.sm),
    );
  }
}

class _DetailPropertyTile extends StatelessWidget {
  final Map<String, dynamic> property;
  final VoidCallback onTap;
  const _DetailPropertyTile({required this.property, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final total = (property['total_price'] as num?)?.toDouble() ?? 0;
    final area = (property['area'] as num?)?.toDouble() ?? 0;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(HMRadius.sm),
      child: Container(
        padding: const EdgeInsets.all(HMSpace.sm),
        decoration: BoxDecoration(
          color: color.surfaceContainerHighest.withValues(alpha: 0.3),
          borderRadius: BorderRadius.circular(HMRadius.sm),
        ),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: color.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(HMRadius.sm),
              ),
              child: Icon(Icons.home_rounded, color: color.primary, size: 20),
            ),
            const SizedBox(width: HMSpace.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    property['community'] as String? ?? '房源',
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 2),
                  Text(
                    '${property['layout']} · ${area.toStringAsFixed(0)}㎡',
                    style: TextStyle(
                      fontSize: 11,
                      color: color.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                ],
              ),
            ),
            Text(
              '${(total / 10000).toStringAsFixed(0)}万',
              style: TextStyle(
                color: color.primary,
                fontSize: 14,
                fontWeight: FontWeight.w700,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
            const SizedBox(width: 2),
            Icon(
              Icons.chevron_right_rounded,
              size: 16,
              color: color.onSurface.withValues(alpha: 0.4),
            ),
          ],
        ),
      ),
    );
  }
}
