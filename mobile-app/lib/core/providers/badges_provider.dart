/// 底导 Tab 红点（badge）数据 provider
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/auth_state.dart';
import '../../features/cooperation/cooperation_service.dart';
import '../../features/cooperation/cooperation_models.dart';
import '../../features/invitation/invitation_service.dart';
import '../../features/invitation/invitation_models.dart';

/// 每个底导 Tab 的 badge 数字
///
/// 哲学：**只显示"待处理"**（需要我点击/确认/拒绝/评价的事项），
/// 不显示"已发起等对方"的（那种已经在 App 里看得到了）。
class TabBadges {
  /// 需求 Tab：固定 0（"我发起的邀请"不需要我处理，对方跟进状态在列表里能看到）
  final int demandsBadge;

  /// 房源 Tab：固定 0（暂未启用）
  final int propertiesBadge;

  /// 合作 Tab：我需要处理的事项总数
  /// = 卖方收到 pending 邀请
  /// + 买方收到 proposal_review 方案
  /// + 我需要评价的合作
  final int cooperationsBadge;

  const TabBadges({
    required this.demandsBadge,
    required this.propertiesBadge,
    required this.cooperationsBadge,
  });

  static const empty = TabBadges(
    demandsBadge: 0,
    propertiesBadge: 0,
    cooperationsBadge: 0,
  );
}

/// 全局 badge provider - 把 3 个 API 汇总成 1 个状态
///
/// 关键：watch [authProvider] 的 userId，切换身份时自动重算。
/// 否则会出现"切了 user 但红点没变"的 bug（实测遇到过）。
final tabBadgesProvider = FutureProvider.autoDispose<TabBadges>((ref) async {
  // 订阅 userId 变化：切换身份时这个 provider 会被销毁重建
  ref.watch(authProvider.select((a) => a.userId));

  // 并发拉取合作 + 邀请（作为买方和卖方）
  final results = await Future.wait([
    ref.read(cooperationServiceProvider).listMy(),
    ref.read(invitationServiceProvider).listMyInvitations(role: 'buyer'),
    ref.read(invitationServiceProvider).listMyInvitations(role: 'seller'),
  ]);

  final coops = results[0] as List<Cooperation>;
  final myBuyerInvs = results[1] as List<Invitation>;
  final mySellerInvs = results[2] as List<Invitation>;

  // 合作 Tab：只算"需要我点"的事项
  // - 卖方收到 pending 邀请 → 要接单 / 拒绝
  // - 买方收到 proposal_review 方案 → 要确认 / 拒绝
  // - 任何方需要评价的合作（handshaked + 还有一方没评）
  final sellerPendingToAct = mySellerInvs.where((i) => i.status == 'pending').length;
  final buyerProposalToReview = myBuyerInvs.where((i) => i.status == 'proposal_review').length;
  final coopsToReview = coops
      .where((c) => !(c.buyerReviewed && c.sellerReviewed))
      .length;

  return TabBadges(
    demandsBadge: 0, // 见上面类注释：发起方不需要主动处理
    propertiesBadge: 0,
    cooperationsBadge: sellerPendingToAct + buyerProposalToReview + coopsToReview,
  );
});
