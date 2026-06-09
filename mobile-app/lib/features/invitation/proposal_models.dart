/// 合作方案数据模型
library;

class Proposal {
  final int id;
  final int invitationId;
  final String content;
  final String? fitPoints;
  final String? viewingSuggestion;
  final String? ownerSituation;
  final DateTime submittedAt;
  final DateTime? confirmedAt;
  final DateTime? declinedAt;
  final String? declineReason;

  const Proposal({
    required this.id,
    required this.invitationId,
    required this.content,
    this.fitPoints,
    this.viewingSuggestion,
    this.ownerSituation,
    required this.submittedAt,
    this.confirmedAt,
    this.declinedAt,
    this.declineReason,
  });

  factory Proposal.fromJson(Map<String, dynamic> json) => Proposal(
        id: json['id'] as int,
        invitationId: json['invitation_id'] as int,
        content: json['content'] as String,
        fitPoints: json['fit_points'] as String?,
        viewingSuggestion: json['viewing_suggestion'] as String?,
        ownerSituation: json['owner_situation'] as String?,
        submittedAt: DateTime.parse(json['submitted_at'] as String),
        confirmedAt: json['confirmed_at'] != null
            ? DateTime.parse(json['confirmed_at'] as String)
            : null,
        declinedAt: json['declined_at'] != null
            ? DateTime.parse(json['declined_at'] as String)
            : null,
        declineReason: json['decline_reason'] as String?,
      );
}
