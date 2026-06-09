/// 需求服务 - API 调用

library;
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/dio_client.dart';
import 'demand_models.dart';

class DemandService {
  DemandService(this._dio);
  final Dio _dio;

  Future<List<Demand>> listMyDemands() async {
    final resp = await _dio.get('/v1/demands');
    final data = resp.data['data'] as List;
    return data.map((d) => Demand.fromJson(d as Map<String, dynamic>)).toList();
  }

  Future<Demand> getDemand(int demandId) async {
    final resp = await _dio.get('/v1/demands/$demandId');
    return Demand.fromJson(resp.data['data'] as Map<String, dynamic>);
  }

  Future<Demand> createDemand({
    required String district,
    required double priceMin,
    required double priceMax,
    required List<String> layouts,
    required String qualification,
    required List<String> viewingTime,
    String? sourceUrl,
  }) async {
    final resp = await _dio.post('/v1/demands', data: {
      'district': district,
      'price_min': priceMin,
      'price_max': priceMax,
      'layouts': layouts,
      'qualification': qualification,
      'viewing_time': viewingTime,
      if (sourceUrl != null) 'source_url': sourceUrl,
    });
    return Demand.fromJson(resp.data['data'] as Map<String, dynamic>);
  }

  Future<List<SellerRecommendation>> getRecommendations(int demandId) async {
    final resp = await _dio.get('/v1/demands/$demandId/recommendations');
    final sellers = (resp.data['data']['sellers'] as List).cast<Map<String, dynamic>>();
    return sellers.map(SellerRecommendation.fromJson).toList();
  }

  /// 发起邀请
  Future<int> runInvitation({
    required int demandId,
    required int sellerId,
    String? note,
  }) async {
    final resp = await _dio.post('/v1/invitations', data: {
      'demand_id': demandId,
      'seller_id': sellerId,
      if (note != null) 'note': note,
    });
    return (resp.data['data'] as Map)['id'] as int;
  }

  /// 下架需求（软删除 + status=closed）
  Future<void> closeDemand(int demandId) async {
    await _dio.delete('/v1/demands/$demandId');
  }
}

final demandServiceProvider = Provider<DemandService>((ref) {
  return DemandService(ref.read(dioProvider));
});
