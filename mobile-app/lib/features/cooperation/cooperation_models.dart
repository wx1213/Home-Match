/// 合作数据模型
class Cooperation {
  final int id;
  final int invitationId;
  final int buyerId;
  final int sellerId;
  final String status;
  final String memoContent;
  final DateTime signedAt;
  final DateTime? closedAt;
  final String? closeReason;
  final bool buyerReviewed;
  final bool sellerReviewed;

  const Cooperation({
    required this.id,
    required this.invitationId,
    required this.buyerId,
    required this.sellerId,
    required this.status,
    required this.memoContent,
    required this.signedAt,
    this.closedAt,
    this.closeReason,
    required this.buyerReviewed,
    required this.sellerReviewed,
  });

  factory Cooperation.fromJson(Map<String, dynamic> json) => Cooperation(
        id: json['id'] as int,
        invitationId: json['invitation_id'] as int,
        buyerId: json['buyer_id'] as int,
        sellerId: json['seller_id'] as int,
        status: json['status'] as String,
        memoContent: json['memo_content'] as String,
        signedAt: DateTime.parse(json['signed_at'] as String),
        closedAt: json['closed_at'] != null
            ? DateTime.parse(json['closed_at'] as String)
            : null,
        closeReason: json['close_reason'] as String?,
        buyerReviewed: json['buyer_reviewed'] as bool? ?? false,
        sellerReviewed: json['seller_reviewed'] as bool? ?? false,
      );
}
