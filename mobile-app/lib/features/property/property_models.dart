/// 房源数据模型
class Property {
  final int id;
  final int sellerId;
  final String community;
  final String layout;
  final double area;
  final double totalPrice;
  final List<String> tags;
  final List<String> images;
  final String viewingTime;
  final String? sourceUrl;
  final bool isVerified;
  final String status;
  final DateTime createdAt;

  const Property({
    required this.id,
    required this.sellerId,
    required this.community,
    required this.layout,
    required this.area,
    required this.totalPrice,
    required this.tags,
    required this.images,
    required this.viewingTime,
    this.sourceUrl,
    required this.isVerified,
    required this.status,
    required this.createdAt,
  });

  factory Property.fromJson(Map<String, dynamic> json) => Property(
        id: json['id'] as int,
        sellerId: json['seller_id'] as int,
        community: json['community'] as String,
        layout: json['layout'] as String,
        area: (json['area'] as num).toDouble(),
        totalPrice: (json['total_price'] as num).toDouble(),
        tags: (json['tags'] as List?)?.cast<String>() ?? [],
        images: (json['images'] as List?)?.cast<String>() ?? [],
        viewingTime: json['viewing_time'] as String,
        sourceUrl: json['source_url'] as String?,
        isVerified: json['is_verified'] as bool? ?? false,
        status: json['status'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
