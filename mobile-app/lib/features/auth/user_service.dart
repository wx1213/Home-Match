/// 用户信息服务
library;

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/dio_client.dart';
import 'auth_state.dart';

class UserStats {
  final int demandCount;
  final int propertyCount;
  final int cooperationCount;
  final int completedCount;
  final int reviewGivenCount;
  final int reviewReceivedCount;
  final double creditScore;
  final double ratingAvg;
  final int ratingCount;
  final int activityCount30d;

  const UserStats({
    required this.demandCount,
    required this.propertyCount,
    required this.cooperationCount,
    required this.completedCount,
    required this.reviewGivenCount,
    required this.reviewReceivedCount,
    required this.creditScore,
    required this.ratingAvg,
    required this.ratingCount,
    required this.activityCount30d,
  });

  factory UserStats.fromJson(Map<String, dynamic> json) => UserStats(
        demandCount: json['demand_count'] as int,
        propertyCount: json['property_count'] as int,
        cooperationCount: json['cooperation_count'] as int,
        completedCount: json['completed_count'] as int,
        reviewGivenCount: json['review_given_count'] as int,
        reviewReceivedCount: json['review_received_count'] as int,
        creditScore: (json['credit_score'] as num).toDouble(),
        ratingAvg: (json['rating_avg'] as num).toDouble(),
        ratingCount: json['rating_count'] as int,
        activityCount30d: json['activity_count_30d'] as int,
      );
}

class UserService {
  UserService(this._dio);
  final Dio _dio;

  Future<UserStats> getMyStats() async {
    final resp = await _dio.get('/v1/users/me/stats');
    return UserStats.fromJson(resp.data['data'] as Map<String, dynamic>);
  }
}

final userServiceProvider = Provider<UserService>((ref) {
  return UserService(ref.read(dioProvider));
});

final myStatsProvider = FutureProvider.autoDispose<UserStats>((ref) async {
  // 切换身份时自动重算
  ref.watch(authProvider.select((a) => a.userId));
  return ref.read(userServiceProvider).getMyStats();
});
