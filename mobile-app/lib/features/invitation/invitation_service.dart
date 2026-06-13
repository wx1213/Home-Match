/// 邀请服务

library;
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/dio_client.dart';
import 'invitation_models.dart';
import 'proposal_models.dart';

class InvitationService {
  InvitationService(this._dio);
  final Dio _dio;

  Future<List<Invitation>> listMyInvitations({String role = 'buyer'}) async {
    final resp = await _dio.get('/v1/invitations', queryParameters: {'role': role});
    final data = resp.data['data'] as List;
    return data.map((d) => Invitation.fromJson(d as Map<String, dynamic>)).toList();
  }

  Future<Invitation> getInvitation(int id) async {
    final resp = await _dio.get('/v1/invitations/$id');
    return Invitation.fromJson(resp.data['data'] as Map<String, dynamic>);
  }

  Future<Invitation> acceptInvitation(int id) async {
    // [Sprint3 修复] accept 响应是简化的 InvitationAcceptResponse
    //   （只有 invitation_id + status + proposal_deadline），
    //   直接 fromJson 完整 Invitation 会因缺 id/demand_id/buyer_id 等 cast null 失败
    // 修法：accept 后调 getInvitation 拿完整对象（跟 rejectInvitation 一致）
    await _dio.post('/v1/invitations/$id/accept');
    return getInvitation(id);
  }

  Future<Invitation> rejectInvitation(int id, {String? reason}) async {
    await _dio.post(
      '/v1/invitations/$id/reject',
      queryParameters: reason != null ? {'reason': reason} : null,
    );
    return getInvitation(id);
  }

  /// 买方确认方案 → 触发握手
  Future<CooperationRef> confirmProposal(int id) async {
    final resp = await _dio.post('/v1/invitations/$id/confirm');
    return CooperationRef.fromJson(resp.data['data'] as Map<String, dynamic>);
  }

  /// 买方拒绝方案
  Future<Invitation> declineProposal(int id, {String? reason}) async {
    await _dio.post(
      '/v1/invitations/$id/decline',
      queryParameters: reason != null ? {'reason': reason} : null,
    );
    return getInvitation(id);
  }

  /// 查询方案（双方都可见）
  Future<Proposal> getProposal(int invitationId) async {
    final resp = await _dio.get('/v1/invitations/$invitationId/proposal');
    return Proposal.fromJson(resp.data['data'] as Map<String, dynamic>);
  }

  /// 提交合作方案（卖方接单后 2h 内）
  Future<Proposal> submitProposal(
    int invitationId, {
    required String content,
    String? fitPoints,
    String? viewingSuggestion,
    String? ownerSituation,
  }) async {
    final resp = await _dio.post(
      '/v1/invitations/$invitationId/proposal',
      data: {
        'content': content,
        if (fitPoints != null) 'fit_points': fitPoints,
        if (viewingSuggestion != null) 'viewing_suggestion': viewingSuggestion,
        if (ownerSituation != null) 'owner_situation': ownerSituation,
      },
    );
    return Proposal.fromJson(resp.data['data'] as Map<String, dynamic>);
  }
}

/// 握手后返回的合作引用（轻量，不展开）
class CooperationRef {
  final int id;
  final String status;
  const CooperationRef({required this.id, required this.status});
  factory CooperationRef.fromJson(Map<String, dynamic> json) => CooperationRef(
        id: json['id'] as int,
        status: json['status'] as String,
      );
}

final invitationServiceProvider = Provider<InvitationService>((ref) {
  return InvitationService(ref.read(dioProvider));
});
