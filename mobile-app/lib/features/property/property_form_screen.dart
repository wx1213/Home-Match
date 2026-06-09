/// 发布房源表单

library;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'property_service.dart';

class PropertyFormScreen extends ConsumerStatefulWidget {
  const PropertyFormScreen({super.key});

  @override
  ConsumerState<PropertyFormScreen> createState() => _PropertyFormScreenState();
}

class _PropertyFormScreenState extends ConsumerState<PropertyFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _communityCtl = TextEditingController();
  final _areaCtl = TextEditingController(text: '90');
  final _priceCtl = TextEditingController(text: '420');
  String _layout = '3室1厅';
  String _viewingTime = '工作日晚上+周末';
  final _tags = <String>{};
  bool _isVerified = false;
  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _communityCtl.dispose();
    _areaCtl.dispose();
    _priceCtl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await ref.read(propertyServiceProvider).createProperty(
            community: _communityCtl.text.trim(),
            layout: _layout,
            area: double.parse(_areaCtl.text),
            totalPrice: double.parse(_priceCtl.text) * 10000,
            tags: _tags.toList(),
            images: const [],
            viewingTime: _viewingTime,
            isVerified: _isVerified,
          );
      if (mounted) context.pop();
    } catch (e) {
      setState(() {
        _error = '发布失败: $e';
        _submitting = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('发布房源')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _communityCtl,
                decoration: const InputDecoration(
                  labelText: '小区名',
                  hintText: '如：望京西园',
                  prefixIcon: Icon(Icons.location_city),
                ),
                validator: (v) => (v == null || v.isEmpty) ? '请输入小区名' : null,
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: _layout,
                decoration: const InputDecoration(labelText: '户型'),
                items: ['1室1厅', '2室1厅', '3室1厅', '3室2厅', '4室+']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (v) => setState(() => _layout = v!),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _areaCtl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: '面积（m²）'),
                      validator: (v) => (v == null || v.isEmpty) ? '必填' : null,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextFormField(
                      controller: _priceCtl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: '总价（万）'),
                      validator: (v) => (v == null || v.isEmpty) ? '必填' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<String>(
                initialValue: _viewingTime,
                decoration: const InputDecoration(labelText: '可看时间'),
                items: ['工作日白天', '工作日晚上', '工作日晚上+周末', '周末', '随时']
                    .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                    .toList(),
                onChanged: (v) => setState(() => _viewingTime = v!),
              ),
              const SizedBox(height: 16),
              const Text('核心标签', style: TextStyle(fontSize: 14)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: ['满五唯一', '近地铁', '南北通透', '采光好', '精装修', '学区房']
                    .map((s) => FilterChip(
                          label: Text(s),
                          selected: _tags.contains(s),
                          onSelected: (sel) => setState(() {
                            if (sel) {
                              _tags.add(s);
                            } else {
                              _tags.remove(s);
                            }
                          }),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 16),
              SwitchListTile(
                title: const Text('已实勘且真实在售'),
                subtitle: const Text('承诺房源真实（必勾选）'),
                value: _isVerified,
                onChanged: (v) => setState(() => _isVerified = v),
                contentPadding: EdgeInsets.zero,
              ),
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ],
              const SizedBox(height: 32),
              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: _submitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('提交'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
