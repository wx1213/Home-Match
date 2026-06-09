/// 房源详情
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/network/dio_client.dart';
import '../../core/theme/app_tokens.dart';
import '../../core/widgets/credit_badge.dart';
import '../../core/widgets/status_chip.dart';
import '../auth/auth_state.dart';
import 'property_models.dart';
import 'property_service.dart';

final _propertyDetailProvider =
    FutureProvider.autoDispose.family<Property, int>((ref, id) async {
  ref.watch(authProvider.select((a) => a.userId));
  return ref.read(propertyServiceProvider).getProperty(id);
});

/// 拉取卖家公开名片（用于显示真实姓名）
final _sellerBriefProvider =
    FutureProvider.autoDispose.family<_SellerBrief, int>((ref, sellerId) async {
  ref.watch(authProvider.select((a) => a.userId));
  final resp = await ref.read(dioProvider).get(
    '/v1/users/batch',
    queryParameters: {'ids': '$sellerId'},
  );
  final list = (resp.data['data'] as List).cast<Map<String, dynamic>>();
  if (list.isEmpty) {
    return _SellerBrief(id: sellerId, displayName: null, creditScore: 0);
  }
  final u = list.first;
  return _SellerBrief(
    id: u['id'] as int,
    displayName: u['display_name'] as String?,
    creditScore: (u['credit_score'] as num?)?.toDouble() ?? 0,
  );
});

class _SellerBrief {
  final int id;
  final String? displayName;
  final double creditScore;
  const _SellerBrief({
    required this.id,
    required this.displayName,
    required this.creditScore,
  });
}

class PropertyDetailScreen extends ConsumerWidget {
  final int propertyId;
  const PropertyDetailScreen({super.key, required this.propertyId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_propertyDetailProvider(propertyId));
    final color = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('房源详情'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(_propertyDetailProvider(propertyId)),
          ),
          IconButton(
            tooltip: '编辑',
            icon: const Icon(Icons.edit_rounded),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('编辑功能 - 待实现')),
              );
            },
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('加载失败: $e')),
        data: (p) {
          final meta = propertyStatusMeta(p.status);
          final priceWan = (p.totalPrice / 10000).toStringAsFixed(0);
          return ListView(
            padding: EdgeInsets.zero,
            children: [
              // 顶部图片占位
              _ImagePlaceholder(
                images: p.images,
                property: p,
              ),
              Padding(
                padding: const EdgeInsets.all(HMSpace.md),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // 价格 + 状态
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(
                          priceWan,
                          style: TextStyle(
                            color: color.primary,
                            fontSize: 32,
                            fontWeight: FontWeight.w700,
                            fontFeatures: const [FontFeature.tabularFigures()],
                          ),
                        ),
                        Padding(
                          padding: const EdgeInsets.only(left: 4, bottom: 4),
                          child: Text(
                            '万',
                            style: TextStyle(
                              color: color.onSurface.withValues(alpha: 0.7),
                              fontSize: 14,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                        const SizedBox(width: HMSpace.sm),
                        StatusChip(
                          label: meta.label,
                          color: meta.color,
                          icon: meta.icon,
                          filled: true,
                        ),
                        const Spacer(),
                        if (p.isVerified)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: HMColors.success.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(HMRadius.sm),
                            ),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.verified_rounded, size: 14, color: HMColors.success),
                                SizedBox(width: 3),
                                Text(
                                  '已实勘',
                                  style: TextStyle(
                                    color: HMColors.success,
                                    fontSize: 11,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: HMSpace.sm),
                    Text(
                      p.community,
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w600,
                        height: 1.3,
                      ),
                    ),
                    const SizedBox(height: HMSpace.xs),
                    Text(
                      '${p.layout} · ${p.area}㎡',
                      style: TextStyle(
                        fontSize: 14,
                        color: color.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                    const SizedBox(height: HMSpace.md),
                    // 关键数据
                    Container(
                      padding: const EdgeInsets.symmetric(vertical: HMSpace.sm),
                      decoration: BoxDecoration(
                        color: color.surfaceContainerHighest.withValues(alpha: 0.4),
                        borderRadius: BorderRadius.circular(HMRadius.md),
                      ),
                      child: Row(
                        children: [
                          _Metric(label: '户型', value: p.layout),
                          _MetricDivider(),
                          _Metric(label: '面积', value: '${p.area.toStringAsFixed(0)}㎡'),
                          _MetricDivider(),
                          _Metric(label: '单价', value: '${((p.totalPrice / p.area).round())}\n元/㎡', isSmall: true),
                        ],
                      ),
                    ),
                    const SizedBox(height: HMSpace.md),
                    // 标签
                    if (p.tags.isNotEmpty) ...[
                      const _SectionTitle(icon: Icons.local_offer_outlined, title: '核心标签'),
                      const SizedBox(height: HMSpace.xs),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: p.tags.map((t) => HMTag(label: t, color: color.primary)).toList(),
                      ),
                      const SizedBox(height: HMSpace.md),
                    ],
                    // 可看时间
                    const _SectionTitle(icon: Icons.access_time_rounded, title: '可看时间'),
                    const SizedBox(height: HMSpace.xs),
                    Text(
                      p.viewingTime,
                      style: const TextStyle(fontSize: 14),
                    ),
                    const SizedBox(height: HMSpace.md),
                    // 源链接（如有）
                    if (p.sourceUrl != null && p.sourceUrl!.isNotEmpty) ...[
                      const _SectionTitle(icon: Icons.link_rounded, title: '来源链接'),
                      const SizedBox(height: HMSpace.xs),
                      Container(
                        padding: const EdgeInsets.all(HMSpace.sm),
                        decoration: BoxDecoration(
                          color: color.surfaceContainerHighest.withValues(alpha: 0.4),
                          borderRadius: BorderRadius.circular(HMRadius.sm),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.link, size: 14),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                p.sourceUrl!,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFF1976D2),
                                  decoration: TextDecoration.underline,
                                ),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: HMSpace.md),
                    ],
                    // 卖家信息（拉真实账号名）
                    const _SectionTitle(icon: Icons.person_outline, title: '维护经纪人'),
                    const SizedBox(height: HMSpace.sm),
                    _SellerInfoRow(sellerId: p.sellerId, createdAt: p.createdAt),
                    const SizedBox(height: HMSpace.xl),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _ImagePlaceholder extends StatelessWidget {
  final List<String> images;
  final Property property;
  const _ImagePlaceholder({required this.images, required this.property});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    if (images.isEmpty) {
      return Container(
        height: 240,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [color.primary, color.primary.withValues(alpha: 0.4)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Stack(
          children: [
            Center(
              child: Icon(
                Icons.home_rounded,
                size: 80,
                color: Colors.white.withValues(alpha: 0.5),
              ),
            ),
            // 房源编号 + 占位提示
            Positioned(
              bottom: HMSpace.md,
              left: HMSpace.md,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(HMRadius.full),
                ),
                child: Text(
                  '${property.layout} · 暂无图片',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ),
            Positioned(
              bottom: HMSpace.md,
              right: HMSpace.md,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(HMRadius.full),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.image_outlined, size: 12, color: Colors.white),
                    SizedBox(width: 3),
                    Text(
                      '0/N',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      );
    }
    // 有图片时用 PageView（实际项目可接入 cached_network_image）
    return SizedBox(
      height: 240,
      child: PageView.builder(
        itemCount: images.length,
        itemBuilder: (_, i) => Container(
          color: Colors.grey.shade300,
          child: Center(child: Text('图片 ${i + 1}')),
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final IconData icon;
  final String title;
  const _SectionTitle({required this.icon, required this.title});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 16, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: 6),
        Text(
          title,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;
  final bool isSmall;
  const _Metric({required this.label, required this.value, this.isSmall = false});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: isSmall ? 13 : 16,
              fontWeight: FontWeight.w700,
              color: Theme.of(context).colorScheme.primary,
              fontFeatures: const [FontFeature.tabularFigures()],
              height: 1.3,
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

class _MetricDivider extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 0.5,
      height: 32,
      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.1),
    );
  }
}

/// 房源详情页里的"维护经纪人"行 - 用真实账号名
class _SellerInfoRow extends ConsumerWidget {
  final int sellerId;
  final DateTime createdAt;
  const _SellerInfoRow({required this.sellerId, required this.createdAt});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = Theme.of(context).colorScheme;
    final asyncSeller = ref.watch(_sellerBriefProvider(sellerId));

    return Row(
      children: [
        // 头像用真实 display_name 生成
        HMUserAvatar(
          name: asyncSeller.maybeWhen(
            data: (s) => s.displayName ?? '经纪人$sellerId',
            orElse: () => '经纪人$sellerId',
          ),
          size: 40,
        ),
        const SizedBox(width: HMSpace.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              asyncSeller.when(
                data: (s) => Text(
                  s.displayName ?? '经纪人 #$sellerId',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                loading: () => const Text(
                  '加载中…',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                ),
                error: (_, __) => Text(
                  '经纪人 #$sellerId',
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '上传于 ${DateFormat('yyyy-MM-dd HH:mm').format(createdAt.toLocal())}',
                style: TextStyle(
                  fontSize: 12,
                  color: color.onSurface.withValues(alpha: 0.6),
                ),
              ),
            ],
          ),
        ),
        // 信用分徽章
        asyncSeller.maybeWhen(
          data: (s) => s.creditScore > 0
              ? CreditBadge(score: s.creditScore, showLabel: false)
              : const SizedBox.shrink(),
          orElse: () => const SizedBox.shrink(),
        ),
      ],
    );
  }
}
