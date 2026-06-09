/// 需求数据模型
class Demand {
  final int id;
  final int buyerId;
  final String district;
  final double priceMin;
  final double priceMax;
  final List<String> layouts;
  final String qualification;
  final List<String> viewingTime;
  final String? sourceUrl;
  final String status;
  final String? summary;
  final DateTime createdAt;

  const Demand({
    required this.id,
    required this.buyerId,
    required this.district,
    required this.priceMin,
    required this.priceMax,
    required this.layouts,
    required this.qualification,
    required this.viewingTime,
    this.sourceUrl,
    required this.status,
    this.summary,
    required this.createdAt,
  });

  factory Demand.fromJson(Map<String, dynamic> json) => Demand(
        id: json['id'] as int,
        buyerId: json['buyer_id'] as int,
        district: json['district'] as String,
        priceMin: (json['price_min'] as num).toDouble(),
        priceMax: (json['price_max'] as num).toDouble(),
        layouts: (json['layouts'] as List?)?.cast<String>() ?? [],
        qualification: json['qualification'] as String? ?? '不限',
        viewingTime: (json['viewing_time'] as List?)?.cast<String>() ?? [],
        sourceUrl: json['source_url'] as String?,
        status: json['status'] as String,
        summary: json['summary'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

/// 推荐卖方
class SellerRecommendation {
  final int rank;
  final double matchScore;
  final Map<String, dynamic> seller;
  final List<Map<String, dynamic>> matchedProperties;

  const SellerRecommendation({
    required this.rank,
    required this.matchScore,
    required this.seller,
    required this.matchedProperties,
  });

  factory SellerRecommendation.fromJson(Map<String, dynamic> json) =>
      SellerRecommendation(
        rank: json['rank'] as int,
        matchScore: (json['match_score'] as num).toDouble(),
        seller: json['seller'] as Map<String, dynamic>,
        matchedProperties: (json['matched_properties'] as List?)
                ?.cast<Map<String, dynamic>>() ??
            [],
      );
}
