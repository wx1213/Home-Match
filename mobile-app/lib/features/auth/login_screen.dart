/// 登录页 - MVP 简化版
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/router/app_router.dart';
import '../../core/network/dio_client.dart';
import '../../core/theme/app_tokens.dart';
import 'auth_service.dart';
import 'auth_state.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  bool _loading = false;
  String? _error;

  Future<void> _login(String code) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final auth = await ref.read(authServiceProvider).loginWithWechat(code);
      final storage = ref.read(secureStorageProvider);
      await storage.write(key: 'access_token', value: auth.accessToken);
      await storage.write(key: 'refresh_token', value: auth.refreshToken);
      ref.read(authProvider.notifier).login(
            userId: auth.userId!,
            userName: auth.userName!,
            displayName: auth.displayName,
            avatarUrl: auth.avatarUrl,
            creditScore: auth.creditScore,
            accessToken: auth.accessToken!,
            refreshToken: auth.refreshToken!,
          );
      ref.read(isLoggedInProvider.notifier).state = true;
      if (mounted) context.go('/demands');
    } catch (e) {
      setState(() {
        _error = '登录失败: $e';
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    return Scaffold(
      body: Stack(
        children: [
          // 顶部渐变背景
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            height: MediaQuery.of(context).size.height * 0.5,
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    color.primary,
                    color.primary.withValues(alpha: 0.85),
                    color.primary.withValues(alpha: 0.6),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
            ),
          ),
          // 装饰圆
          Positioned(
            top: -100,
            right: -80,
            child: Container(
              width: 280,
              height: 280,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.08),
                shape: BoxShape.circle,
              ),
            ),
          ),
          Positioned(
            top: 80,
            left: -60,
            child: Container(
              width: 200,
              height: 200,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.06),
                shape: BoxShape.circle,
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32),
              child: _loading
                  ? const Center(child: CircularProgressIndicator(color: Colors.white))
                  : Column(
                      children: [
                        const SizedBox(height: HMSpace.xxl + HMSpace.lg),
                        // Logo
                        Container(
                          width: 88,
                          height: 88,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(HMRadius.xxl),
                            boxShadow: HMShadow.level3,
                          ),
                          child: Icon(
                            Icons.home_work_rounded,
                            size: 48,
                            color: color.primary,
                          ),
                        ),
                        const SizedBox(height: HMSpace.lg),
                        const Text(
                          'Home Match',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 32,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.5,
                          ),
                        ),
                        const SizedBox(height: HMSpace.xs),
                        Text(
                          '北京独立经纪人撮合平台',
                          style: TextStyle(
                            color: Colors.white.withValues(alpha: 0.9),
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: HMSpace.xxl + HMSpace.lg),
                        if (_error != null) ...[
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: HMSpace.md,
                              vertical: HMSpace.sm,
                            ),
                            decoration: BoxDecoration(
                              color: color.errorContainer.withValues(alpha: 0.9),
                              borderRadius: BorderRadius.circular(HMRadius.sm),
                            ),
                            child: Text(
                              _error!,
                              style: TextStyle(color: color.onErrorContainer, fontSize: 13),
                              textAlign: TextAlign.center,
                            ),
                          ),
                          const SizedBox(height: HMSpace.md),
                        ],
                        // 微信登录按钮
                        FilledButton.icon(
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(52),
                            backgroundColor: Colors.white,
                            foregroundColor: color.primary,
                            textStyle: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          onPressed: _loading
                              ? null
                              : () => _login(
                                  'dev_test_code_${DateTime.now().millisecondsSinceEpoch}',
                                ),
                          icon: Icon(Icons.wechat_rounded, color: HMColors.success),
                          label: const Text('微信登录 (开发模式)'),
                        ),
                        const SizedBox(height: HMSpace.sm),
                        // 短信登录
                        OutlinedButton.icon(
                          style: OutlinedButton.styleFrom(
                            minimumSize: const Size.fromHeight(52),
                            foregroundColor: Colors.white,
                            side: BorderSide(color: Colors.white.withValues(alpha: 0.5)),
                            textStyle: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                          onPressed: _loading
                              ? null
                              : () => _login(
                                  'sms_login_${DateTime.now().millisecondsSinceEpoch}',
                                ),
                          icon: const Icon(Icons.sms_outlined),
                          label: const Text('短信验证码登录 (兜底)'),
                        ),
                        const Spacer(),
                        // 底部版本号
                        Padding(
                          padding: const EdgeInsets.only(bottom: HMSpace.lg),
                          child: Column(
                            children: [
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Container(
                                    width: 32,
                                    height: 1,
                                    color: color.onSurface.withValues(alpha: 0.2),
                                  ),
                                  Padding(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: HMSpace.sm,
                                    ),
                                    child: Text(
                                      '登录即表示同意',
                                      style: TextStyle(
                                        fontSize: 11,
                                        color: color.onSurface.withValues(alpha: 0.5),
                                      ),
                                    ),
                                  ),
                                  Container(
                                    width: 32,
                                    height: 1,
                                    color: color.onSurface.withValues(alpha: 0.2),
                                  ),
                                ],
                              ),
                              const SizedBox(height: HMSpace.xs),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    '《服务协议》',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: color.primary,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  Text(
                                    '  ·  ',
                                    style: TextStyle(
                                      color: color.onSurface.withValues(alpha: 0.3),
                                    ),
                                  ),
                                  Text(
                                    '《隐私政策》',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: color.primary,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: HMSpace.xs),
                              Text(
                                'v0.4 · MVP 验证版',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: color.onSurface.withValues(alpha: 0.3),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }
}
