/// 方案详情 - 双方都可以看
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_tokens.dart';
import '../../core/widgets/empty_state.dart';
import 'invitation_service.dart';
import 'proposal_models.dart';

final _proposalProvider =
    FutureProvider.family<Proposal, int>((ref, invId) async {
  return ref.read(invitationServiceProvider).getProposal(invId);
});

class ProposalViewScreen extends ConsumerWidget {
  final int invitationId;
  const ProposalViewScreen({super.key, required this.invitationId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_proposalProvider(invitationId));
    final color = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('合作方案'),
        actions: [
          IconButton(
            tooltip: '刷新',
            icon: const Icon(Icons.refresh_rounded),
            onPressed: () => ref.invalidate(_proposalProvider(invitationId)),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorState(
          message: '$e',
          onRetry: () => ref.invalidate(_proposalProvider(invitationId)),
        ),
        data: (p) {
          return ListView(
            padding: const EdgeInsets.all(HMSpace.md),
            children: [
              // 提交时间
              Container(
                padding: const EdgeInsets.all(HMSpace.md),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [color.primary, color.primary.withValues(alpha: 0.7)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(HMRadius.lg),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.25),
                        borderRadius: BorderRadius.circular(HMRadius.md),
                      ),
                      child: const Icon(Icons.description_rounded, color: Colors.white, size: 26),
                    ),
                    const SizedBox(width: HMSpace.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            '已提交合作方案',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            DateFormat('yyyy-MM-dd HH:mm').format(p.submittedAt.toLocal()),
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.9),
                              fontSize: 13,
                            ),
                          ),
                          if (p.confirmedAt != null) ...[
                            const SizedBox(height: 2),
                            Text(
                              '✅ 买方已于 ${DateFormat('MM-dd HH:mm').format(p.confirmedAt!.toLocal())} 确认',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ] else if (p.declinedAt != null) ...[
                            const SizedBox(height: 2),
                            Text(
                              '❌ 买方已于 ${DateFormat('MM-dd HH:mm').format(p.declinedAt!.toLocal())} 拒绝',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: HMSpace.md),

              // 方案内容
              _Section(
                title: '方案内容',
                icon: Icons.assignment_rounded,
                child: SelectableText(
                  p.content,
                  style: const TextStyle(
                    fontSize: 14,
                    height: 1.6,
                  ),
                ),
              ),
              if (p.fitPoints != null && p.fitPoints!.isNotEmpty) ...[
                const SizedBox(height: HMSpace.md),
                _Section(
                  title: '卖方优势',
                  icon: Icons.star_rate_rounded,
                  child: Text(
                    p.fitPoints!,
                    style: const TextStyle(fontSize: 14, height: 1.6),
                  ),
                ),
              ],
              if (p.viewingSuggestion != null && p.viewingSuggestion!.isNotEmpty) ...[
                const SizedBox(height: HMSpace.md),
                _Section(
                  title: '看房建议',
                  icon: Icons.event_available_rounded,
                  child: Text(
                    p.viewingSuggestion!,
                    style: const TextStyle(fontSize: 14, height: 1.6),
                  ),
                ),
              ],
              if (p.ownerSituation != null && p.ownerSituation!.isNotEmpty) ...[
                const SizedBox(height: HMSpace.md),
                _Section(
                  title: '业主情况',
                  icon: Icons.person_outline_rounded,
                  child: Text(
                    p.ownerSituation!,
                    style: const TextStyle(fontSize: 14, height: 1.6),
                  ),
                ),
              ],
              if (p.declineReason != null && p.declineReason!.isNotEmpty) ...[
                const SizedBox(height: HMSpace.md),
                Container(
                  padding: const EdgeInsets.all(HMSpace.md),
                  decoration: BoxDecoration(
                    color: HMColors.statusRejected.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(HMRadius.md),
                    border: Border.all(
                      color: HMColors.statusRejected.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.cancel_outlined,
                          color: HMColors.statusRejected, size: 20),
                      const SizedBox(width: HMSpace.xs),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              '买方拒绝原因',
                              style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: HMColors.statusRejected,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              p.declineReason!,
                              style: const TextStyle(fontSize: 14, height: 1.5),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: HMSpace.xl),
            ],
          );
        },
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;
  const _Section({required this.title, required this.icon, required this.child});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(HMSpace.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 18, color: color.primary),
                const SizedBox(width: 6),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: HMSpace.sm),
            child,
          ],
        ),
      ),
    );
  }
}
