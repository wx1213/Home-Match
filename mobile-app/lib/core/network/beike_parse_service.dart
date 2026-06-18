/// 贝壳链接解析 service（P0 任务 1 - B2 commit）
///
/// 调后端 POST /v1/ai/parse-beike-url，返 BeikeParseResult。
/// [D-009] MVP：仅 URL 校验 + 房源 ID 提取，不调 LLM 解析内容。
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'api_exception.dart';
import 'dio_client.dart';

/// 贝壳 URL 解析结果（对应后端 /v1/ai/parse-beike-url 返 data 字段）
class BeikeParseResult {
  final bool valid;
  final String? urlType; // 'ershoufang' / 'loupan' / 'buyhouse' / 'xinfang'
  final String? houseId;
  final String? city;
  final String? reason; // 失败原因（valid=false 时有值）

  const BeikeParseResult({
    required this.valid,
    this.urlType,
    this.houseId,
    this.city,
    this.reason,
  });

  /// 中文类型标签（用于 UI 展示）
  String? get typeLabel {
    switch (urlType) {
      case 'ershoufang':
        return '二手房';
      case 'loupan':
        return '楼盘';
      case 'buyhouse':
        return '购房需求';
      case 'xinfang':
        return '新房';
      default:
        return null;
    }
  }

  /// 城市中文标签（如 "bj" → "北京"）
  String? get cityLabel {
    const cityMap = {
      'bj': '北京',
      'sh': '上海',
      'gz': '广州',
      'sz': '深圳',
      'hz': '杭州',
      'cd': '成都',
      'wh': '武汉',
      'nj': '南京',
      'cs': '长沙',
      'xa': '西安',
      'tj': '天津',
      'cq': '重庆',
    };
    return city == null ? null : cityMap[city];
  }

  /// UI 预览文案（"北京-二手房 #12345"）
  String? get previewLabel {
    if (!valid) return null;
    final parts = <String>[];
    final city = cityLabel;
    if (city != null) parts.add(city);
    final type = typeLabel;
    if (type != null) parts.add(type);
    if (houseId != null) parts.add('#$houseId');
    return parts.isEmpty ? '已识别' : parts.join('-');
  }

  factory BeikeParseResult.fromJson(Map<String, dynamic> json) {
    return BeikeParseResult(
      valid: json['valid'] as bool? ?? false,
      urlType: json['url_type'] as String?,
      houseId: json['house_id'] as String?,
      city: json['city'] as String?,
      reason: json['reason'] as String?,
    );
  }
}

/// 贝壳链接解析 service
class BeikeParseService {
  BeikeParseService(this._dio);
  final Dio _dio;

  /// 解析贝壳 URL。失败抛 ApiException。
  Future<BeikeParseResult> parse(String url) async {
    try {
      final resp = await _dio.post(
        '/v1/ai/parse-beike-url',
        data: {'url': url},
      );
      final apiResp = ApiResponse.fromJson(
        resp.data as Map<String, dynamic>,
        (data) => data as Map<String, dynamic>,
      );
      if (!apiResp.isOk) {
        throw ApiException(
          code: apiResp.code,
          message: apiResp.message,
        );
      }
      return BeikeParseResult.fromJson(apiResp.data!);
    } on DioException catch (e) {
      throw ApiException(
        code: -1,
        message: '网络错误: ${e.message}',
        httpStatus: e.response?.statusCode,
      );
    }
  }
}

/// Riverpod provider
final beikeParseServiceProvider = Provider<BeikeParseService>((ref) {
  return BeikeParseService(ref.read(dioProvider));
});