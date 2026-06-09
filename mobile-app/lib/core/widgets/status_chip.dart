/// 通用状态徽章
library;

import 'package:flutter/material.dart';

import '../theme/app_tokens.dart';

/// 状态徽章 - 圆角小标签，状态色背景
class StatusChip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;
  final bool filled;

  const StatusChip({
    super.key,
    required this.label,
    required this.color,
    this.icon,
    this.filled = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: filled ? color : color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(HMRadius.full),
        border: filled ? null : Border.all(color: color.withValues(alpha: 0.3), width: 0.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: filled ? Colors.white : color),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: TextStyle(
              color: filled ? Colors.white : color,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

/// 邀请状态 → (label, color, icon) 映射
({String label, Color color, IconData icon}) invitationStatusMeta(String status) {
  switch (status) {
    case 'pending':
      return (label: '待响应', color: HMColors.statusPending, icon: Icons.schedule);
    case 'accepted':
      return (label: '已接单', color: HMColors.statusAccepted, icon: Icons.check_circle_outline);
    case 'proposal_review':
      return (label: '方案待审', color: HMColors.statusProposal, icon: Icons.description_outlined);
    case 'handshaked':
      return (label: '已握手', color: HMColors.statusHandshaked, icon: Icons.handshake);
    case 'rejected':
      return (label: '已拒绝', color: HMColors.statusRejected, icon: Icons.cancel_outlined);
    case 'expired':
      return (label: '已超时', color: HMColors.statusExpired, icon: Icons.timer_off_outlined);
    case 'closed':
      return (label: '已关闭', color: HMColors.statusExpired, icon: Icons.archive_outlined);
    default:
      return (label: status, color: HMColors.statusExpired, icon: Icons.help_outline);
  }
}

/// 房源状态 → (label, color, icon) 映射
({String label, Color color, IconData icon}) propertyStatusMeta(String status) {
  switch (status) {
    case 'active':
      return (label: '上架中', color: HMColors.success, icon: Icons.bolt);
    case 'frozen':
      return (label: '已冻结', color: HMColors.statusRejected, icon: Icons.ac_unit);
    case 'delisted':
      return (label: '已下架', color: HMColors.statusExpired, icon: Icons.remove_circle_outline);
    default:
      return (label: status, color: HMColors.statusExpired, icon: Icons.help_outline);
  }
}

/// 合作状态 → (label, color, icon) 映射
({String label, Color color, IconData icon}) cooperationStatusMeta(String status) {
  switch (status) {
    case 'handshaked':
      return (label: '已握手', color: HMColors.statusHandshaked, icon: Icons.handshake);
    case 'in_progress':
      return (label: '进行中', color: HMColors.statusAccepted, icon: Icons.timelapse);
    case 'completed':
      return (label: '已完成', color: HMColors.success, icon: Icons.task_alt);
    case 'terminated':
      return (label: '已终止', color: HMColors.statusRejected, icon: Icons.block);
    default:
      return (label: status, color: HMColors.statusExpired, icon: Icons.help_outline);
  }
}

/// 需求状态 → (label, color, icon) 映射
({String label, Color color, IconData icon}) demandStatusMeta(String status) {
  switch (status) {
    case 'active':
      return (label: '匹配中', color: HMColors.success, icon: Icons.search);
    case 'matched':
      return (label: '已匹配', color: HMColors.statusAccepted, icon: Icons.check_circle_outline);
    case 'closed':
      return (label: '已关闭', color: HMColors.statusExpired, icon: Icons.flag_outlined);
    default:
      return (label: status, color: HMColors.statusExpired, icon: Icons.help_outline);
  }
}

/// 通用 Tag - 用于显示房源标签等
class HMTag extends StatelessWidget {
  final String label;
  final Color? color;
  final IconData? icon;
  final bool filled;

  const HMTag({
    super.key,
    required this.label,
    this.color,
    this.icon,
    this.filled = false,
  });

  @override
  Widget build(BuildContext context) {
    final c = color ?? Theme.of(context).colorScheme.primary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: filled ? c : c.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(HMRadius.sm),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: filled ? Colors.white : c),
            const SizedBox(width: 3),
          ],
          Text(
            label,
            style: TextStyle(
              color: filled ? Colors.white : c,
              fontSize: 11,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

/// 渐变头像 - 用户名首字母 + 渐变背景
class HMUserAvatar extends StatelessWidget {
  final String name;
  final double size;
  final String? avatarUrl;

  const HMUserAvatar({
    super.key,
    required this.name,
    this.size = 48,
    this.avatarUrl,
  });

  @override
  Widget build(BuildContext context) {
    final initial = (name.isNotEmpty ? name[0] : '?').toUpperCase();
    // 用名字 hash 选渐变色
    final hash = name.codeUnits.fold<int>(0, (a, b) => a + b);
    final colors = [
      [const Color(0xFF1976D2), const Color(0xFF1565C0)],
      [const Color(0xFF26A69A), const Color(0xFF00897B)],
      [const Color(0xFF7B1FA2), const Color(0xFF6A1B9A)],
      [const Color(0xFFE53935), const Color(0xFFC62828)],
      [const Color(0xFFF57C00), const Color(0xFFEF6C00)],
      [const Color(0xFF5E35B1), const Color(0xFF4527A0)],
    ];
    final c = colors[hash % colors.length];

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: c,
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        shape: BoxShape.circle,
      ),
      alignment: Alignment.center,
      child: Text(
        initial,
        style: TextStyle(
          color: Colors.white,
          fontSize: size * 0.4,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
