/// 邀请数据模型
class Invitation {
  final int id;
  final int demandId;
  final int buyerId;
  final int sellerId;
  final String status;
  final DateTime expiredAt;
  final DateTime? respondedAt;
  final DateTime? proposalDeadline;
  final String? rejectReason;
  final String? note;
  final DateTime createdAt;

  const Invitation({
    required this.id,
    required this.demandId,
    required this.buyerId,
    required this.sellerId,
    required this.status,
    required this.expiredAt,
    this.respondedAt,
    this.proposalDeadline,
    this.rejectReason,
    this.note,
    required this.createdAt,
  });

  factory Invitation.fromJson(Map<String, dynamic> json) => Invitation(
        id: json['id'] as int,
        demandId: json['demand_id'] as int,
        buyerId: json['buyer_id'] as int,
        sellerId: json['seller_id'] as int,
        status: json['status'] as String,
        expiredAt: DateTime.parse(json['expired_at'] as String),
        respondedAt: json['responded_at'] != null
            ? DateTime.parse(json['responded_at'] as String)
            : null,
        proposalDeadline: json['proposal_deadline'] != null
            ? DateTime.parse(json['proposal_deadline'] as String)
            : null,
        rejectReason: json['reject_reason'] as String?,
        note: json['note'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
