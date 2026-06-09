/// 合作仪表板用的工具 widgets - 用户摘要 / 需求摘要
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/network/dio_client.dart';
import '../../../core/theme/app_tokens.dart';
import '../../../core/widgets/status_chip.dart';
import '../../auth/auth_state.dart';
import '../../demand/demand_models.dart';
import '../../demand/demand_service.dart';

/// 拉取公开用户名片（按 ids 缓存）
final _publicUserBriefProvider =
    FutureProvider.autoDispose.family<_PublicUserBrief, int>(
  (ref, userId) async {
    ref.watch(authProvider.select((a) => a.userId));
    final resp = await ref
        .read(dioProvider)
        .get('/v1/users/batch', queryParameters: {'ids': '$userId'});
    final list = (resp.data['data'] as List).cast<Map<String, dynamic>>();
    if (list.isEmpty) {
      return _PublicUserBrief(id: userId, displayName: null, creditScore: 0);
    }
    final u = list.first;
    return _PublicUserBrief(
      id: u['id'] as int,
      displayName: u['display_name'] as String?,
      creditScore: (u['credit_score'] as num?)?.toDouble() ?? 0,
    );
  },
);

class _PublicUserBrief {
  final int id;
  final String? displayName;
  final double creditScore;
  const _PublicUserBrief({
    required this.id,
    required this.displayName,
    required this.creditScore,
  });
}

/// 拉取需求摘要（按 demand_id 缓存）
final _demandSummaryProvider =
    FutureProvider.autoDispose.family<Demand?, int>(
  (ref, demandId) async {
    ref.watch(authProvider.select((a) => a.userId));
    try {
      return await ref.read(demandServiceProvider).getDemand(demandId);
    } catch (_) {
      return null;
    }
  },
);

/// 显示用户（带头像 + 名字 + 角色 tag）
class UserSummary extends ConsumerWidget {
  final int userId;
  final String role; // "买方" or "卖方"
  final Color roleColor;
  const UserSummary({
    super.key,
    required this.userId,
    required this.role,
    required this.roleColor,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_publicUserBriefProvider(userId));
    final color = Theme.of(context).colorScheme;

    return Row(
      children: [
        Text(
          '$role：',
          style: TextStyle(
            fontSize: 12,
            color: color.onSurface.withValues(alpha: 0.6),
          ),
        ),
        HMUserAvatar(
          name: async.maybeWhen(
            data: (u) => u.displayName ?? '用户',
            orElse: () => '用户',
          ),
          size: 20,
        ),
        const SizedBox(width: 4),
        async.when(
          data: (u) => Text(
            u.displayName ?? '用户 #${u.id}',
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
          loading: () => const SizedBox(
            width: 40,
            height: 12,
            child: DecoratedBox(
              decoration: BoxDecoration(color: Color(0x10000000)),
            ),
          ),
          error: (_, __) => Text(
            '用户 #$userId',
            style: const TextStyle(fontSize: 12),
          ),
        ),
        if (async.maybeWhen(
              data: (u) => u.creditScore > 0,
              orElse: () => false,
            )) ...[
          const SizedBox(width: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: roleColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(HMRadius.sm),
            ),
            child: Text(
              '信用 ${async.maybeWhen(data: (u) => u.creditScore.toStringAsFixed(1), orElse: () => '0')}',
              style: TextStyle(
                fontSize: 9,
                color: roleColor,
                fontWeight: FontWeight.w600,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ),
        ],
      ],
    );
  }
}

/// 显示需求摘要（可点击跳转）
class DemandSummary extends ConsumerWidget {
  final int demandId;
  const DemandSummary({super.key, required this.demandId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_demandSummaryProvider(demandId));
    final color = Theme.of(context).colorScheme;

    return InkWell(
      onTap: () => context.push('/demands'),
      borderRadius: BorderRadius.circular(HMRadius.sm),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          children: [
            Text(
              '需求：',
              style: TextStyle(
                fontSize: 12,
                color: color.onSurface.withValues(alpha: 0.6),
              ),
            ),
            Icon(
              Icons.location_on_outlined,
              size: 14,
              color: color.onSurface.withValues(alpha: 0.5),
            ),
            const SizedBox(width: 2),
            async.when(
              data: (d) => Text(
                d == null
                    ? '已删除 #$demandId'
                    : '${d.district} ${(d.priceMin / 10000).toStringAsFixed(0)}-${(d.priceMax / 10000).toStringAsFixed(0)}万',
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
              ),
              loading: () => const SizedBox(
                width: 60,
                height: 12,
                child: DecoratedBox(
                  decoration: BoxDecoration(color: Color(0x10000000)),
                ),
              ),
              error: (_, __) => Text(
                '#$demandId',
                style: const TextStyle(fontSize: 12),
              ),
            ),
            if (async.maybeWhen(
                  data: (d) => d?.layouts.isNotEmpty == true,
                  orElse: () => false,
                )) ...[
              const SizedBox(width: 4),
              Text(
                async.maybeWhen(
                  data: (d) => d?.layouts.take(2).join('/') ?? '',
                  orElse: () => '',
                ),
                style: TextStyle(
                  fontSize: 11,
                  color: color.onSurface.withValues(alpha: 0.5),
                ),
              ),
            ],
            const SizedBox(width: 2),
            Icon(
              Icons.chevron_right_rounded,
              size: 14,
              color: color.onSurface.withValues(alpha: 0.3),
            ),
          ],
        ),
      ),
    );
  }
}

/// 显示倒计时（带紧急态变色）
class InvitationCountdown extends StatelessWidget {
  final DateTime deadline;
  const InvitationCountdown({super.key, required this.deadline});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    return StreamBuilder<DateTime>(
      stream: Stream.periodic(const Duration(seconds: 1), (_) => DateTime.now()),
      builder: (context, _) {
        final diff = deadline.difference(DateTime.now());
        if (diff.isNegative) {
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.timer_off_outlined,
                  size: 12, color: color.onSurface.withValues(alpha: 0.4)),
              const SizedBox(width: 3),
              Text(
                '已过期',
                style: TextStyle(
                  fontSize: 11,
                  color: color.onSurface.withValues(alpha: 0.4),
                ),
              ),
            ],
          );
        }
        final urgent = diff.inHours < 1;
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.timer_outlined,
              size: 12,
              color: urgent
                  ? HMColors.statusRejected
                  : color.onSurface.withValues(alpha: 0.5),
            ),
            const SizedBox(width: 3),
            Text(
              '剩 ${_format(diff)}',
              style: TextStyle(
                fontSize: 11,
                color: urgent
                    ? HMColors.statusRejected
                    : color.onSurface.withValues(alpha: 0.6),
                fontWeight: urgent ? FontWeight.w600 : FontWeight.w400,
                fontFeatures: const [FontFeature.tabularFigures()],
              ),
            ),
          ],
        );
      },
    );
  }

  String _format(Duration d) {
    if (d.inDays >= 1) return '${d.inDays}天${d.inHours % 24}小时';
    if (d.inHours >= 1) return '${d.inHours}:${(d.inMinutes % 60).toString().padLeft(2, '0')}';
    return '${d.inMinutes}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';
  }
}
