/// 邀请列表（Tab 切换 buyer/seller）

library;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/widgets/empty_state.dart';
import '../auth/auth_state.dart';
import 'invitation_models.dart';
import 'invitation_service.dart';
import 'invitation_detail_screen.dart';

final _invitationsProvider =
    FutureProvider.autoDispose.family<List<Invitation>, String>(
  (ref, role) {
    ref.watch(authProvider.select((a) => a.userId));
    return ref.read(invitationServiceProvider).listMyInvitations(role: role);
  },
);

class InvitationsScreen extends ConsumerStatefulWidget {
  const InvitationsScreen({super.key});

  @override
  ConsumerState<InvitationsScreen> createState() => _InvitationsScreenState();
}

class _InvitationsScreenState extends ConsumerState<InvitationsScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tab;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('邀请'),
        bottom: TabBar(
          controller: _tab,
          tabs: const [
            Tab(text: '我发出的'),
            Tab(text: '我收到的'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tab,
        children: [
          _InvitationsList(role: 'buyer'),
          _InvitationsList(role: 'seller'),
        ],
      ),
    );
  }
}

class _InvitationsList extends ConsumerWidget {
  final String role;
  const _InvitationsList({required this.role});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_invitationsProvider(role));
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => ErrorState(
        message: '加载失败: $e',
        onRetry: () => ref.invalidate(_invitationsProvider(role)),
      ),
      data: (list) {
        if (list.isEmpty) {
          return EmptyState(
            icon: Icons.send_outlined,
            title: '还没有邀请',
            subtitle: role == 'buyer' ? '去推荐页发起邀请' : '等待买方邀请你',
          );
        }
        return RefreshIndicator(
          onRefresh: () async => ref.invalidate(_invitationsProvider(role)),
          child: ListView.builder(
            itemCount: list.length,
            itemBuilder: (_, i) => _InvitationTile(inv: list[i], role: role),
          ),
        );
      },
    );
  }
}

class _InvitationTile extends ConsumerWidget {
  final Invitation inv;
  final String role;
  const _InvitationTile({required this.inv, required this.role});

  Color _statusColor() {
    return switch (inv.status) {
      'pending' => Colors.orange,
      'accepted' => Colors.blue,
      'proposal_review' => Colors.purple,
      'handshaked' => Colors.green,
      'rejected' => Colors.red,
      'expired' => Colors.grey,
      'closed' => Colors.grey,
      _ => Colors.grey,
    };
  }

  String _statusLabel() {
    return switch (inv.status) {
      'pending' => '待响应',
      'accepted' => '已接单',
      'proposal_review' => '方案待审',
      'handshaked' => '已握手',
      'rejected' => '已拒绝',
      'expired' => '已超时',
      'closed' => '已关闭',
      _ => inv.status,
    };
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final color = _statusColor();
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: color.withValues(alpha: 0.1),
        child: Icon(
          role == 'buyer' ? Icons.send : Icons.inbox,
          color: color,
        ),
      ),
      title: Text('邀请 #${inv.id}'),
      subtitle: Text(
        '${_statusLabel()} · ${inv.createdAt.toString().substring(0, 16)}',
      ),
      trailing: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(_statusLabel(), style: TextStyle(color: color, fontSize: 12)),
      ),
      onTap: () {
        // Navigate to detail
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => InvitationDetailScreen(invitationId: inv.id),
          ),
        );
      },
    );
  }
}
