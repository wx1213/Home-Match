/// 发布需求表单

library;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/beike_parse_service.dart';
import '../../core/widgets/paste_link_button.dart';
import 'demand_service.dart';

class DemandFormScreen extends ConsumerStatefulWidget {
  const DemandFormScreen({super.key});

  @override
  ConsumerState<DemandFormScreen> createState() => _DemandFormScreenState();
}

class _DemandFormScreenState extends ConsumerState<DemandFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _districtCtl = TextEditingController();
  final _priceMinCtl = TextEditingController(text: '350');
  final _priceMaxCtl = TextEditingController(text: '450');
  final _sourceUrlCtl = TextEditingController(); // P0 任务 1：贝壳链接
  BeikeParseResult? _parsedBeike;                // 解析后的预览数据
  String _qualification = '首套';
  final _layouts = <String>{'3室1厅'};
  final _viewingTime = <String>{'工作日晚上', '周末'};

  bool _submitting = false;
  String? _error;

  @override
  void dispose() {
    _districtCtl.dispose();
    _priceMinCtl.dispose();
    _priceMaxCtl.dispose();
    _sourceUrlCtl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_layouts.isEmpty) {
      setState(() => _error = '请至少选择一个户型');
      return;
    }
    if (_viewingTime.isEmpty) {
      setState(() => _error = '请至少选择一个看房时间');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await ref.read(demandServiceProvider).createDemand(
            district: _districtCtl.text.trim(),
            priceMin: double.parse(_priceMinCtl.text) * 10000,
            priceMax: double.parse(_priceMaxCtl.text) * 10000,
            layouts: _layouts.toList(),
            qualification: _qualification,
            viewingTime: _viewingTime.toList(),
            sourceUrl: _sourceUrlCtl.text.trim().isEmpty
                ? null
                : _sourceUrlCtl.text.trim(),
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
      appBar: AppBar(title: const Text('发布需求')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // ====== P0 任务 1：贝壳链接粘贴入口 ======
              PasteLinkButton(
                onParsed: (url, result) {
                  setState(() {
                    _sourceUrlCtl.text = url;
                    _parsedBeike = result;
                  });
                },
              ),
              if (_parsedBeike != null) ...[
                const SizedBox(height: 8),
                BeikePreviewCard(
                  url: _sourceUrlCtl.text,
                  result: _parsedBeike!,
                  onClear: () {
                    setState(() {
                      _sourceUrlCtl.clear();
                      _parsedBeike = null;
                    });
                  },
                ),
              ],
              const SizedBox(height: 16),

              TextFormField(
                controller: _districtCtl,
                decoration: const InputDecoration(
                  labelText: '区域',
                  hintText: '如：朝阳区',
                  prefixIcon: Icon(Icons.location_on_outlined),
                ),
                validator: (v) => (v == null || v.isEmpty) ? '请输入区域' : null,
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      controller: _priceMinCtl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: '总价下限（万）',
                      ),
                      validator: (v) => (v == null || v.isEmpty) ? '必填' : null,
                    ),
                  ),
                  const Padding(padding: EdgeInsets.symmetric(horizontal: 8), child: Text('~')),
                  Expanded(
                    child: TextFormField(
                      controller: _priceMaxCtl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: '总价上限（万）',
                      ),
                      validator: (v) => (v == null || v.isEmpty) ? '必填' : null,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              const Text('户型（可多选）', style: TextStyle(fontSize: 14)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: ['1室1厅', '2室1厅', '3室1厅', '3室2厅', '4室+']
                    .map((s) => FilterChip(
                          label: Text(s),
                          selected: _layouts.contains(s),
                          onSelected: (sel) => setState(() {
                            if (sel) {
                              _layouts.add(s);
                            } else {
                              _layouts.remove(s);
                            }
                          }),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 16),
              const Text('购房资质', style: TextStyle(fontSize: 14)),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: '首套', label: Text('首套')),
                  ButtonSegment(value: '二套', label: Text('二套')),
                  ButtonSegment(value: '不限', label: Text('不限')),
                ],
                selected: {_qualification},
                onSelectionChanged: (s) => setState(() => _qualification = s.first),
              ),
              const SizedBox(height: 16),
              const Text('看房时间偏好（可多选）', style: TextStyle(fontSize: 14)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: ['工作日白天', '工作日晚上', '周末', '随时']
                    .map((s) => FilterChip(
                          label: Text(s),
                          selected: _viewingTime.contains(s),
                          onSelected: (sel) => setState(() {
                            if (sel) {
                              _viewingTime.add(s);
                            } else {
                              _viewingTime.remove(s);
                            }
                          }),
                        ))
                    .toList(),
              ),
              if (_error != null) ...[
                const SizedBox(height: 16),
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
                    : const Text('发布并查看推荐'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
