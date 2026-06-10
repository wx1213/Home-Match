/// 个人中心
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_state.dart';
import '../auth/user_service.dart';
import '../../core/router/app_router.dart';
import '../../core/network/dio_client.dart';
import '../../core/theme/app_tokens.dart';
import '../../core/widgets/credit_badge.dart';
import '../../core/widgets/status_chip.dart';
import '../../main.dart' show switchDevUser;

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final statsAsync = ref.watch(myStatsProvider);
    final color = Theme.of(context).colorScheme;
    final name = auth.displayName ?? auth.userName ?? '未登录';

    return Scaffold(
      appBar: AppBar(
        title: const Text('我的'),
        actions: [
          IconButton(
            tooltip: '切换身份（开发模式）',
            icon: const Icon(Icons.bug_report_outlined),
            onPressed: () => _showDevSwitcher(context, ref),
          ),
          IconButton(
            tooltip: '退出登录',
            icon: const Icon(Icons.logout_rounded),
            onPressed: () => _confirmLogout(context, ref),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(myStatsProvider);
          try {
            await ref.read(myStatsProvider.future);
          } catch (_) {}
        },
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            // 头部：渐变背景 + 头像 + 信用分
            _ProfileHeader(name: name, userId: auth.userId, creditScore: auth.creditScore),
            const SizedBox(height: HMSpace.lg),
            // 信用分详情（基于 stats）
            statsAsync.maybeWhen(
              data: (stats) => _Section(
                title: '信用分',
                children: [
                  _CreditDetailTile(stats: stats),
                ],
              ),
              orElse: () => const SizedBox.shrink(),
            ),
            // 功能菜单
            _Section(
              title: '账户与设置',
              children: [
                _MenuTile(
                  icon: Icons.notifications_outlined,
                  title: '通知设置',
                  onTap: () {},
                ),
                _MenuTile(
                  icon: Icons.verified_user_outlined,
                  title: '实名认证',
                  trailing: StatusChip(
                    label: auth.creditScore != null && auth.creditScore! >= 60 ? '已认证' : '未认证',
                    color: auth.creditScore != null && auth.creditScore! >= 60
                        ? HMColors.success
                        : HMColors.warning,
                  ),
                  onTap: () {},
                ),
                _MenuTile(
                  icon: Icons.security_rounded,
                  title: '隐私政策',
                  onTap: () {},
                ),
              ],
            ),
            _Section(
              title: '关于',
              children: [
                _MenuTile(
                  icon: Icons.info_outline_rounded,
                  title: '关于 Home Match',
                  subtitle: 'v0.4 · MVP 验证版',
                  onTap: () {
                    showAboutDialog(
                      context: context,
                      applicationName: 'Home Match',
                      applicationVersion: '0.4.0',
                      applicationLegalese: '北京独立经纪人撮合平台',
                    );
                  },
                ),
                _MenuTile(
                  icon: Icons.help_outline_rounded,
                  title: '反馈与帮助',
                  onTap: () {},
                ),
              ],
            ),
            const SizedBox(height: HMSpace.lg),
            Center(
              child: Text(
                '© 2026 Home Match',
                style: TextStyle(
                  fontSize: 11,
                  color: color.onSurface.withValues(alpha: 0.3),
                ),
              ),
            ),
            const SizedBox(height: HMSpace.xl),
          ],
        ),
      ),
    );
  }

  /// 开发模式身份切换器
  /// 退出登录二次确认
  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        icon: const Icon(Icons.logout_rounded, size: 32),
        title: const Text('退出登录？'),
        content: const Text('退出后需要重新登录才能继续使用。\n（开发模式下可用 🐛 切换身份）'),
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
            child: const Text('确认退出'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    ref.read(authProvider.notifier).logout();
    ref.read(isLoggedInProvider.notifier).state = false;
    final storage = ref.read(secureStorageProvider);
    await storage.delete(key: 'access_token');
    await storage.delete(key: 'refresh_token');
    // 重要：保留 last_dev_code，下次启动用回同一身份自动登录（开发便利）
    if (context.mounted) context.go('/login');
  }

  void _showDevSwitcher(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (sheetCtx) {
        return Container(
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surface,
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
                  Center(
                    child: Container(
                      width: 36,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: HMSpace.md),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  Row(
                    children: [
                      Icon(Icons.bug_report_outlined,
                          size: 18, color: Theme.of(context).colorScheme.primary),
                      const SizedBox(width: 6),
                      const Text(
                        '开发模式 · 切换身份',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                  const SizedBox(height: HMSpace.xs),
                  Text(
                    '选择后立即用该 wechat code 重新登录；邀请 / 合作 / 评价等业务会自动按 user_id 区分。',
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                  const SizedBox(height: HMSpace.md),
                  Flexible(
                    child: SingleChildScrollView(
                      child: Consumer(
                        builder: (context, ref, _) {
                          final asyncIdentities = ref.watch(devIdentitiesProvider);
                          return asyncIdentities.when(
                            loading: () => const Padding(
                              padding: EdgeInsets.all(HMSpace.md),
                              child: Center(child: CircularProgressIndicator()),
                            ),
                            error: (e, _) => Padding(
                              padding: const EdgeInsets.all(HMSpace.md),
                              child: Text('加载失败: $e'),
                            ),
                            data: (identities) {
                              if (identities.isEmpty) {
                                return const Padding(
                                  padding: EdgeInsets.all(HMSpace.md),
                                  child: Text('暂无 dev 身份'),
                                );
                              }
                              return Column(
                                children: identities.map((id) {
                                  return _DevUserTile(
                                    identity: id,
                                    onTap: () async {
                                      Navigator.of(sheetCtx).pop();
                                      final container = ProviderScope.containerOf(context);
                                      await switchDevUser(container, id.code);
                                      if (context.mounted) {
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          SnackBar(
                                            content: Text('已切换到 ${id.displayName ?? id.roleLabel}'),
                                            behavior: SnackBarBehavior.floating,
                                          ),
                                        );
                                        context.go('/demands');
                                      }
                                    },
                                  );
                                }).toList(),
                              );
                            },
                          );
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
}

/// 切换器里的一张卡片：显示真实账号名（从后端拉）
///
/// P1-0 修复：突出显示 user_id，避免「dev_seller_7 ≠ user 7」的心智错位
class _DevUserTile extends ConsumerWidget {
  final DevIdentity identity;
  final VoidCallback onTap;
  const _DevUserTile({required this.identity, required this.onTap});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = Theme.of(context).colorScheme;
    final id = identity;

    return Container(
      margin: const EdgeInsets.only(bottom: HMSpace.xs),
      decoration: BoxDecoration(
        color: color.surfaceContainerHighest.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(HMRadius.md),
      ),
      child: ListTile(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(HMRadius.md),
        ),
        // 头像用真实 display_name 生成
        leading: HMUserAvatar(
          name: id.displayName ?? id.name ?? id.code,
          size: 36,
        ),
        // 标题：#userId 徽章 + display_name（id 在前显眼）
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: color.primaryContainer,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                '#${id.userId}',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: color.onPrimaryContainer,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                id.displayName ?? '用户',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        // 副标题：roleLabel · 信用分 · 业务数据
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 2),
          child: Text(
            '${id.roleLabel} · 信用 ${id.creditScore.toStringAsFixed(1)} '
            '· 需求 ${id.demandCount} / 房源 ${id.propertyCount}',
            style: const TextStyle(fontSize: 11),
          ),
        ),
        // 右上角再放一个 dev code 小标（hover 提示）
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            const Icon(Icons.login_rounded, size: 18),
            const SizedBox(height: 2),
            Text(
              id.code,
              style: TextStyle(
                fontSize: 9,
                color: color.onSurface.withValues(alpha: 0.5),
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ],
        ),
        onTap: onTap,
      ),
    );
  }
}

class _UserBrief {
  final int id;
  final String? displayName;
  final double creditScore;
  const _UserBrief({
    required this.id,
    required this.displayName,
    required this.creditScore,
  });
}

/// 公开名片拉取 provider（按 ids 字符串缓存）
final devUsersBriefProvider = FutureProvider.family<List<_UserBrief>, String>(
  (ref, ids) async {
    if (ids.isEmpty) return const [];
    final resp = await ref.read(dioProvider).get(
      '/v1/users/batch',
      queryParameters: {'ids': ids},
    );
    final data = (resp.data['data'] as List).cast<Map<String, dynamic>>();
    return data
        .map((m) => _UserBrief(
              id: m['id'] as int,
              displayName: m['display_name'] as String?,
              creditScore: (m['credit_score'] as num?)?.toDouble() ?? 0,
            ))
        .toList();
  },
);

/// 动态 dev 身份 - 从后端拉所有 mock 模式创建的用户
class DevIdentity {
  final String code;
  final int userId;
  final String? displayName;
  final String? name;
  final double creditScore;
  final bool isVerified;
  final String role;
  final String roleLabel;
  final int demandCount;
  final int propertyCount;

  const DevIdentity({
    required this.code,
    required this.userId,
    required this.displayName,
    required this.name,
    required this.creditScore,
    required this.isVerified,
    required this.role,
    required this.roleLabel,
    required this.demandCount,
    required this.propertyCount,
  });

  factory DevIdentity.fromJson(Map<String, dynamic> json) => DevIdentity(
        code: json['code'] as String,
        userId: json['user_id'] as int,
        displayName: json['display_name'] as String?,
        name: json['name'] as String?,
        creditScore: (json['credit_score'] as num?)?.toDouble() ?? 0,
        isVerified: json['is_verified'] as bool? ?? false,
        role: json['role'] as String? ?? 'unknown',
        roleLabel: json['role_label'] as String? ?? '',
        demandCount: json['demand_count'] as int? ?? 0,
        propertyCount: json['property_count'] as int? ?? 0,
      );
}

final devIdentitiesProvider = FutureProvider.autoDispose<List<DevIdentity>>((ref) async {
  // 切换身份时也要刷新
  ref.watch(authProvider.select((a) => a.userId));
  final resp = await ref.read(dioProvider).get('/v1/users/dev-identities');
  final data = (resp.data['data'] as List).cast<Map<String, dynamic>>();
  return data.map(DevIdentity.fromJson).toList();
});

// ============================================================
//  头部（渐变 + 头像 + 数据看板）
// ============================================================

class _ProfileHeader extends ConsumerWidget {
  final String name;
  final int? userId;
  final double? creditScore;
  const _ProfileHeader({required this.name, required this.userId, required this.creditScore});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = Theme.of(context).colorScheme;
    final statsAsync = ref.watch(myStatsProvider);

    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [color.primary, color.primary.withValues(alpha: 0.7)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(
            HMSpace.md, HMSpace.lg, HMSpace.md, HMSpace.lg,
          ),
          child: Column(
            children: [
              Row(
                children: [
                  HMUserAvatar(name: name, size: 64),
                  const SizedBox(width: HMSpace.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          name,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(HMRadius.sm),
                              ),
                              child: Text(
                                'ID: ${userId ?? "?"}',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: HMSpace.xs),
                        if (creditScore != null)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(HMRadius.full),
                            ),
                            child: CreditBadge(score: creditScore!),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: HMSpace.lg),
              // 数据看板（实时统计）
              statsAsync.when(
                data: (stats) => _StatsRow(stats: stats),
                loading: () => const _StatsRowSkeleton(),
                error: (_, __) => _StatsRowError(color: Colors.white),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatsRow extends StatelessWidget {
  final UserStats stats;
  const _StatsRow({required this.stats});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _Stat(label: '需求', value: '${stats.demandCount}', color: Colors.white),
        const _StatDivider(color: Colors.white),
        _Stat(label: '房源', value: '${stats.propertyCount}', color: Colors.white),
        const _StatDivider(color: Colors.white),
        _Stat(
          label: '合作',
          value: '${stats.cooperationCount + stats.completedCount}',
          color: Colors.white,
          subtitle: stats.completedCount > 0 ? '已完成 ${stats.completedCount}' : null,
        ),
        const _StatDivider(color: Colors.white),
        _Stat(
          label: '评价',
          value: '${stats.reviewReceivedCount}',
          color: Colors.white,
          subtitle: stats.ratingCount > 0
              ? '均 ${stats.ratingAvg.toStringAsFixed(1)} 星'
              : null,
        ),
      ],
    );
  }
}

class _StatsRowSkeleton extends StatelessWidget {
  const _StatsRowSkeleton();
  @override
  Widget build(BuildContext context) {
    return Row(
      children: List.generate(7, (i) {
        if (i.isEven) {
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4),
              child: Container(
                height: 40,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
          );
        }
        return const _StatDivider(color: Colors.white);
      }),
    );
  }
}

class _StatsRowError extends StatelessWidget {
  final Color color;
  const _StatsRowError({required this.color});
  @override
  Widget build(BuildContext context) {
    return Row(
      children: const [
        _Stat(label: '需求', value: '-', color: Colors.white),
        _StatDivider(color: Colors.white),
        _Stat(label: '房源', value: '-', color: Colors.white),
        _StatDivider(color: Colors.white),
        _Stat(label: '合作', value: '-', color: Colors.white),
        _StatDivider(color: Colors.white),
        _Stat(label: '评价', value: '-', color: Colors.white),
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  final String? subtitle;
  const _Stat({
    required this.label,
    required this.value,
    required this.color,
    this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 22,
              fontWeight: FontWeight.w700,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              color: color.withValues(alpha: 0.85),
              fontSize: 11,
            ),
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 1),
            Text(
              subtitle!,
              style: TextStyle(
                color: color.withValues(alpha: 0.65),
                fontSize: 9,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _StatDivider extends StatelessWidget {
  final Color color;
  const _StatDivider({required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 0.5,
      height: 28,
      color: color.withValues(alpha: 0.3),
    );
  }
}

// ============================================================
//  信用分详情（公式可视化 + 引导）
// ============================================================

class _CreditDetailTile extends StatelessWidget {
  final UserStats stats;
  const _CreditDetailTile({required this.stats});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final baseScore = stats.ratingAvg * 20;
    final activityFactor =
        (0.3 + 0.7 * (stats.activityCount30d.clamp(0, 10) / 10)).clamp(0.0, 1.0);
    final hasRatings = stats.ratingCount > 0;

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: HMSpace.md,
        vertical: HMSpace.sm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.calculate_rounded, size: 14, color: color.primary),
              const SizedBox(width: 4),
              Text(
                '计算公式',
                style: TextStyle(
                  fontSize: 11,
                  color: color.onSurface.withValues(alpha: 0.6),
                ),
              ),
            ],
          ),
          const SizedBox(height: HMSpace.xs),
          Text(
            '基础分 × 活跃系数 = ${baseScore.toStringAsFixed(0)} × ${activityFactor.toStringAsFixed(2)}',
            style: const TextStyle(
              fontSize: 13,
              fontFamily: 'monospace',
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: HMSpace.xs),
          Wrap(
            spacing: HMSpace.xs,
            runSpacing: HMSpace.xs,
            children: [
              _FormulaChip(
                label: '评价均分',
                value: stats.ratingCount > 0
                    ? '${stats.ratingAvg.toStringAsFixed(1)} 星'
                    : '暂无',
                icon: Icons.star_rounded,
              ),
              _FormulaChip(
                label: '评价数',
                value: '${stats.ratingCount}',
                icon: Icons.rate_review_rounded,
              ),
              _FormulaChip(
                label: '30天响应',
                value: '${stats.activityCount30d}/10',
                icon: Icons.flash_on_rounded,
                color: stats.activityCount30d >= 10 ? HMColors.success : null,
              ),
              _FormulaChip(
                label: '已完成合作',
                value: '${stats.completedCount}',
                icon: Icons.handshake_rounded,
              ),
            ],
          ),
          if (!hasRatings) ...[
            const SizedBox(height: HMSpace.xs),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: HMSpace.sm,
                vertical: HMSpace.xs,
              ),
              decoration: BoxDecoration(
                color: HMColors.statusPending.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(HMRadius.sm),
              ),
              child: Row(
                children: [
                  const Icon(Icons.lightbulb_outline_rounded,
                      size: 14, color: HMColors.statusPending),
                  const SizedBox(width: 4),
                  const Expanded(
                    child: Text(
                      '完成首次合作并互评，信用分将显著提升',
                      style: TextStyle(
                        fontSize: 11,
                        color: HMColors.statusPending,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _FormulaChip extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color? color;
  const _FormulaChip({
    required this.label,
    required this.value,
    required this.icon,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final c = color ?? Theme.of(context).colorScheme.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: c.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(HMRadius.sm),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: c),
          const SizedBox(width: 4),
          Text(
            '$label ',
            style: TextStyle(
              fontSize: 11,
              color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: c,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================
//  通用：分区 / 菜单项
// ============================================================

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;
  const _Section({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        HMSpace.md, HMSpace.md, HMSpace.md, 0,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: HMSpace.xs, bottom: HMSpace.xs),
            child: Text(
              title,
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.6),
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          Card(
            child: Column(
              children: [
                for (int i = 0; i < children.length; i++) ...[
                  children[i],
                  if (i < children.length - 1)
                    Divider(
                      height: 0.5,
                      thickness: 0.5,
                      indent: HMSpace.md + 48,
                      color: Theme.of(context).dividerColor,
                    ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MenuTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? trailing;
  final VoidCallback onTap;
  const _MenuTile({
    required this.icon,
    required this.title,
    this.subtitle,
    this.trailing,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.5),
          borderRadius: BorderRadius.circular(HMRadius.sm),
        ),
        child: Icon(
          icon,
          size: 18,
          color: Theme.of(context).colorScheme.primary,
        ),
      ),
      title: Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
      subtitle: subtitle != null ? Text(subtitle!, style: const TextStyle(fontSize: 12)) : null,
      trailing: trailing ?? const Icon(Icons.chevron_right_rounded, size: 20),
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: HMSpace.md, vertical: 4),
    );
  }
}
