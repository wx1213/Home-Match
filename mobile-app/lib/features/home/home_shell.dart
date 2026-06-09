/// 主页壳 - 持有 NavigationBar（持久化），内部交给 StatefulShellRoute
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/providers/badges_provider.dart';

/// 各 Tab 的描述（label、icon、active icon、badge 索引）
class _TabSpec {
  final String label;
  final IconData icon;
  final IconData activeIcon;
  const _TabSpec({
    required this.label,
    required this.icon,
    required this.activeIcon,
  });
}

final _tabs = <_TabSpec>[
  _TabSpec(
    label: '需求',
    icon: Icons.search_outlined,
    activeIcon: Icons.search,
  ),
  _TabSpec(
    label: '房源',
    icon: Icons.apartment_outlined,
    activeIcon: Icons.apartment,
  ),
  _TabSpec(
    label: '合作',
    icon: Icons.handshake_outlined,
    activeIcon: Icons.handshake,
  ),
  _TabSpec(
    label: '我的',
    icon: Icons.person_outline,
    activeIcon: Icons.person,
  ),
];

class HomeShell extends ConsumerWidget {
  final StatefulNavigationShell navigationShell;
  const HomeShell({required this.navigationShell, super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncBadges = ref.watch(tabBadgesProvider);
    // 取快照值（即使还在 loading 也用空值，不阻塞 UI）
    final badges = asyncBadges.maybeWhen(
      data: (b) => b,
      orElse: () => TabBadges.empty,
    );

    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (i) {
          // 关键：使用 goBranch 而不是 go，避免重置其他分支的栈
          navigationShell.goBranch(
            i,
            initialLocation: i == navigationShell.currentIndex,
          );
        },
        destinations: _tabs.asMap().entries.map((entry) {
          final i = entry.key;
          final t = entry.value;
          // 根据 Tab 索引取对应 badge 数字
          int count = 0;
          switch (i) {
            case 0:
              count = badges.demandsBadge;
              break;
            case 2:
              count = badges.cooperationsBadge;
              break;
          }
          return NavigationDestination(
            icon: _BadgedIcon(icon: t.icon, count: count),
            selectedIcon: _BadgedIcon(icon: t.activeIcon, count: count),
            label: t.label,
          );
        }).toList(),
      ),
    );
  }
}

/// 带数字红点的图标
class _BadgedIcon extends StatelessWidget {
  final IconData icon;
  final int count;
  const _BadgedIcon({required this.icon, required this.count});

  @override
  Widget build(BuildContext context) {
    if (count <= 0) return Icon(icon);
    final color = Theme.of(context).colorScheme;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Icon(icon),
        Positioned(
          right: -8,
          top: -6,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
            decoration: BoxDecoration(
              color: color.error,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: color.surface, width: 1.5),
            ),
            child: Center(
              child: Text(
                count > 99 ? '99+' : '$count',
                style: TextStyle(
                  color: color.onError,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                  height: 1.1,
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
