/// 合作服务
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/dio_client.dart';
import 'cooperation_models.dart';

class CooperationService {
  CooperationService(this._dio);
  final Dio _dio;

  Future<List<Cooperation>> listMy({String role = 'all'}) async {
    final resp = await _dio.get(
      '/v1/cooperations',
      queryParameters: role == 'all' ? null : {'role': role},
    );
    final data = (resp.data['data'] as List).cast<Map<String, dynamic>>();
    return data.map(Cooperation.fromJson).toList();
  }

  Future<Cooperation> get(int id) async {
    final resp = await _dio.get('/v1/cooperations/$id');
    return Cooperation.fromJson(resp.data['data'] as Map<String, dynamic>);
  }
}

final cooperationServiceProvider = Provider<CooperationService>((ref) {
  return CooperationService(ref.read(dioProvider));
});
