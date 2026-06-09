/// 房源服务

library;
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/dio_client.dart';
import 'property_models.dart';

class PropertyService {
  PropertyService(this._dio);
  final Dio _dio;

  Future<List<Property>> listMyProperties() async {
    final resp = await _dio.get('/v1/properties');
    final data = resp.data['data'] as List;
    return data.map((d) => Property.fromJson(d as Map<String, dynamic>)).toList();
  }

  Future<Property> getProperty(int id) async {
    final resp = await _dio.get('/v1/properties/$id');
    return Property.fromJson(resp.data['data'] as Map<String, dynamic>);
  }

  Future<Property> updateProperty(int id, Map<String, dynamic> patch) async {
    final resp = await _dio.patch('/v1/properties/$id', data: patch);
    return Property.fromJson(resp.data['data'] as Map<String, dynamic>);
  }

  Future<Property> createProperty({
    required String community,
    required String layout,
    required double area,
    required double totalPrice,
    required List<String> tags,
    required List<String> images,
    required String viewingTime,
    String? sourceUrl,
    bool isVerified = false,
  }) async {
    final resp = await _dio.post('/v1/properties', data: {
      'community': community,
      'layout': layout,
      'area': area,
      'total_price': totalPrice,
      'tags': tags,
      'images': images,
      'viewing_time': viewingTime,
      if (sourceUrl != null) 'source_url': sourceUrl,
      'is_verified': isVerified,
    });
    return Property.fromJson(resp.data['data'] as Map<String, dynamic>);
  }

  /// 下架房源（软删除 + status=inactive）
  Future<void> delistProperty(int propertyId) async {
    await _dio.delete('/v1/properties/$propertyId');
  }
}

final propertyServiceProvider = Provider<PropertyService>((ref) {
  return PropertyService(ref.read(dioProvider));
});
