/// 认证状态 - 登录态管理

library;
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AuthState {
  final bool isLoggedIn;
  final int? userId;
  final String? userName;
  final String? displayName;
  final String? avatarUrl;
  final double? creditScore;
  final String? accessToken;
  final String? refreshToken;

  const AuthState({
    this.isLoggedIn = false,
    this.userId,
    this.userName,
    this.displayName,
    this.avatarUrl,
    this.creditScore,
    this.accessToken,
    this.refreshToken,
  });

  AuthState copyWith({
    bool? isLoggedIn,
    int? userId,
    String? userName,
    String? displayName,
    String? avatarUrl,
    double? creditScore,
    String? accessToken,
    String? refreshToken,
  }) {
    return AuthState(
      isLoggedIn: isLoggedIn ?? this.isLoggedIn,
      userId: userId ?? this.userId,
      userName: userName ?? this.userName,
      displayName: displayName ?? this.displayName,
      avatarUrl: avatarUrl ?? this.avatarUrl,
      creditScore: creditScore ?? this.creditScore,
      accessToken: accessToken ?? this.accessToken,
      refreshToken: refreshToken ?? this.refreshToken,
    );
  }

  AuthState cleared() => const AuthState();
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(const AuthState());

  void login({
    required int userId,
    required String userName,
    String? displayName,
    String? avatarUrl,
    double? creditScore,
    required String accessToken,
    required String refreshToken,
  }) {
    state = state.copyWith(
      isLoggedIn: true,
      userId: userId,
      userName: userName,
      displayName: displayName,
      avatarUrl: avatarUrl,
      creditScore: creditScore,
      accessToken: accessToken,
      refreshToken: refreshToken,
    );
  }

  void logout() {
    state = state.cleared();
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier();
});
