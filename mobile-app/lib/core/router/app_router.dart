/// 路由配置 - go_router + StatefulShellRoute（底部 Tab 常驻）
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_event_bus.dart';
import '../../features/auth/auth_state.dart';
import '../../features/auth/login_screen.dart';
import '../../features/cooperation/cooperation_board_screen.dart';
import '../../features/cooperation/cooperation_detail_screen.dart';
import '../../features/demand/demand_form_screen.dart';
import '../../features/demand/demand_list_screen.dart';
import '../../features/demand/recommendations_screen.dart';
import '../../features/home/home_shell.dart';
import '../../features/invitation/invitation_detail_screen.dart';
import '../../features/invitation/invitations_screen.dart';
import '../../features/invitation/proposal_form_screen.dart';
import '../../features/invitation/proposal_view_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/property/property_detail_screen.dart';
import '../../features/property/property_form_screen.dart';
import '../../features/property/property_list_screen.dart';
import '../../features/review/review_form_screen.dart';

/// 当前登录态 provider
final isLoggedInProvider = StateProvider<bool>((ref) => true);

/// Tab 索引常量
const int kTabDemands = 0;
const int kTabProperties = 1;
const int kTabCooperations = 2;
const int kTabProfile = 3;

final routerProvider = Provider<GoRouter>((ref) {
  // 监听全局认证事件总线（401 强制登出时触发）
  final eventListenable = ref.watch(authEventListenableProvider);

  return GoRouter(
    initialLocation: '/demands',
    refreshListenable: eventListenable,
    redirect: (context, state) {
      final bus = ref.read(authEventBusProvider);
      // 如果有强制登出事件 → 清状态 + 跳登录
      if (bus.lastEvent?.forceLogout == true) {
        ref.read(authProvider.notifier).logout();
        ref.read(isLoggedInProvider.notifier).state = false;
        // 重置事件（避免死循环）
        bus.emit(const AuthEvent(forceLogout: false));
        return '/login';
      }
      final isLoggedIn = ref.read(isLoggedInProvider);
      final goingToLogin = state.matchedLocation == '/login';
      if (!isLoggedIn && !goingToLogin) return '/login';
      if (isLoggedIn && goingToLogin) return '/demands';
      return null;
    },
    routes: [
      // 登录
      GoRoute(
        path: '/login',
        builder: (_, __) => const LoginScreen(),
      ),

      // 主壳（带底部 Tab）
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return HomeShell(navigationShell: navigationShell);
        },
        branches: [
          // ============ Tab 0: 需求 ============
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/demands',
                builder: (_, __) => const DemandListScreen(),
                routes: [
                  GoRoute(
                    path: 'new',
                    builder: (_, __) => const DemandFormScreen(),
                  ),
                  GoRoute(
                    path: ':id/recommendations',
                    builder: (_, state) => RecommendationsScreen(
                      demandId: int.parse(state.pathParameters['id']!),
                    ),
                  ),
                ],
              ),
            ],
          ),

          // ============ Tab 1: 房源 ============
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/properties',
                builder: (_, __) => const PropertyListScreen(),
                routes: [
                  GoRoute(
                    path: 'new',
                    builder: (_, __) => const PropertyFormScreen(),
                  ),
                  GoRoute(
                    path: ':id',
                    builder: (_, state) => PropertyDetailScreen(
                      propertyId: int.parse(state.pathParameters['id']!),
                    ),
                  ),
                ],
              ),
            ],
          ),

          // ============ Tab 2: 合作（看板 + 邀请） ============
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/cooperations',
                builder: (_, __) => const CooperationBoardScreen(),
                routes: [
                  GoRoute(
                    path: ':id',
                    builder: (_, state) => CooperationDetailScreen(
                      cooperationId: int.parse(state.pathParameters['id']!),
                    ),
                    routes: [
                      GoRoute(
                        path: 'review',
                        builder: (_, state) => ReviewFormScreen(
                          cooperationId: int.parse(state.pathParameters['id']!),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              GoRoute(
                path: '/invitations',
                builder: (_, __) => const InvitationsScreen(),
                routes: [
                  GoRoute(
                    path: ':id',
                    builder: (_, state) => InvitationDetailScreen(
                      invitationId: int.parse(state.pathParameters['id']!),
                    ),
                    routes: [
                      GoRoute(
                        path: 'proposal',
                        builder: (_, state) => ProposalViewScreen(
                          invitationId: int.parse(state.pathParameters['id']!),
                        ),
                      ),
                      GoRoute(
                        path: 'proposal-new',
                        builder: (_, state) => ProposalFormScreen(
                          invitationId: int.parse(state.pathParameters['id']!),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),

          // ============ Tab 3: 我的 ============
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/profile',
                builder: (_, __) => const ProfileScreen(),
              ),
            ],
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      appBar: AppBar(title: const Text('页面未找到')),
      body: Center(child: Text('路由错误: ${state.error}')),
    ),
  );
});
