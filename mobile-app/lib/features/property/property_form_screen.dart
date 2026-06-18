/// 发布/编辑房源表单
///
/// - 无 propertyId = 创建模式
/// - 有 propertyId = 编辑模式（先 GET 详情，prefill，提交时 PATCH）
///
/// P0 改造（2026-06-10）：
/// - image_picker 选图（相册/拍照）
/// - flutter_image_compress 压缩（单边 ≤1600px，质量 80%）
/// - dio 上传到后端 /v1/upload/image
/// - 缩略图网格展示 + 删除 + 重新排序
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:cached_network_image/cached_network_image.dart';

import '../../core/network/beike_parse_service.dart';
import '../../core/widgets/paste_link_button.dart';
import '../upload/upload_service.dart';
import 'property_models.dart';
import 'property_service.dart';

/// 户型枚举 - 与后端 seed 数据 + 后端 schema 保持一致
const List<String> kLayoutOptions = [
  '1室1厅', '2室1厅', '2室2厅', '3室1厅', '3室2厅', '4室+',
];

class PropertyFormScreen extends ConsumerStatefulWidget {
  /// 编辑模式传 propertyId；null = 创建
  final int? propertyId;
  const PropertyFormScreen({super.key, this.propertyId});

  @override
  ConsumerState<PropertyFormScreen> createState() => _PropertyFormScreenState();
}

class _PropertyFormScreenState extends ConsumerState<PropertyFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _communityCtl = TextEditingController();
  final _areaCtl = TextEditingController(text: '90');
  final _priceCtl = TextEditingController(text: '420');
  final _sourceUrlCtl = TextEditingController(); // P0 任务 1：贝壳链接
  BeikeParseResult? _parsedBeike;                // 解析后的预览数据
  String _layout = '3室1厅';
  String _viewingTime = '工作日晚上+周末';
  final _tags = <String>{};
  bool _isVerified = false;
  bool _submitting = false;
  String? _error;

  // === 图片管理（本地状态：URL 列表） ===
  final List<String> _images = [];
  // 正在上传中的文件名（用于 loading 占位）
  final Set<String> _uploading = {};

  // 编辑模式：标记是否已 prefill（避免重复 fetch）
  bool _prefilled = false;
  // 编辑模式：源数据（用于计算 diff，只 PATCH 改过的字段）
  Property? _original;

  bool get _isEdit => widget.propertyId != null;

  /// 把任意 layout 字符串 sanitize 到 kLayoutOptions 之一
  /// 防止后端返回脏数据（如 "2室2厅" / "4室2厅" 不在选项里）时 dropdown 断言失败
  String _sanitizeLayout(String? raw) {
    if (raw == null) return kLayoutOptions.first;
    if (kLayoutOptions.contains(raw)) return raw;
    // 模糊匹配：把不识别的值归到最接近的选项
    if (raw.contains('4')) return '4室+';
    if (raw.contains('1厅')) return '2室1厅';
    return kLayoutOptions.first;
  }

  @override
  void dispose() {
    _communityCtl.dispose();
    _areaCtl.dispose();
    _priceCtl.dispose();
    _sourceUrlCtl.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    if (_isEdit) {
      _loadForEdit();
    }
  }

  Future<void> _loadForEdit() async {
    try {
      final p = await ref.read(propertyServiceProvider).getProperty(widget.propertyId!);
      if (!mounted) return;
      setState(() {
        _communityCtl.text = p.community;
        _areaCtl.text = p.area.toString();
        _priceCtl.text = (p.totalPrice / 10000).toString();
        _layout = _sanitizeLayout(p.layout);
        _viewingTime = p.viewingTime;
        _sourceUrlCtl.text = p.sourceUrl ?? '';
        _tags
          ..clear()
          ..addAll(p.tags);
        _isVerified = p.isVerified;
        _images
          ..clear()
          ..addAll(p.images);
        _prefilled = true;
        _original = p;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _error = '加载房源失败: $e');
      }
    }
  }

  // ============================================================
  //  图片选择 / 上传 / 移除
  // ============================================================

  Future<void> _pickAndUpload({required ImageSource source}) async {
    if (_images.length >= 9) {
      _toast('最多 9 张图');
      return;
    }
    final remaining = 9 - _images.length;
    final upload = ref.read(uploadServiceProvider);
    final picked = await upload.pickImages(
      maxImages: remaining,
      source: source,
    );
    if (picked.isEmpty) return;

    for (final file in picked) {
      if (_images.length >= 9) break;
      final tempName = 'uploading_${DateTime.now().microsecondsSinceEpoch}';
      setState(() => _uploading.add(tempName));
      try {
        final result = await upload.uploadOne(file);
        if (!mounted) return;
        setState(() {
          _uploading.remove(tempName);
          _images.add(result.url);
        });
      } catch (e) {
        if (!mounted) return;
        setState(() => _uploading.remove(tempName));
        _toast('上传失败: $e');
      }
    }
  }

  void _removeImage(int index) {
    setState(() => _images.removeAt(index));
  }

  void _moveImage(int oldIndex, int newIndex) {
    if (newIndex > oldIndex) newIndex -= 1;
    final item = _images.removeAt(oldIndex);
    _images.insert(newIndex, item);
    setState(() {});
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  // ============================================================
  //  提交
  // ============================================================

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (_images.isEmpty) {
      _toast('请至少上传 1 张房源图');
      return;
    }
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      if (_isEdit) {
        // 编辑：只 PATCH 改过的字段
        final patch = <String, dynamic>{};
        if (_communityCtl.text.trim() != _original?.community) {
          patch['community'] = _communityCtl.text.trim();
        }
        if (_layout != _original?.layout) patch['layout'] = _layout;
        if (double.tryParse(_areaCtl.text) != _original?.area) {
          patch['area'] = double.parse(_areaCtl.text);
        }
        final newPrice = double.parse(_priceCtl.text) * 10000;
        if (newPrice != _original?.totalPrice) patch['total_price'] = newPrice;
        if (_viewingTime != _original?.viewingTime) {
          patch['viewing_time'] = _viewingTime;
        }
        final newTags = _tags.toList();
        if (_tagsSetDiff(newTags.toSet(), (_original?.tags ?? const []).toSet())) {
          patch['tags'] = newTags;
        }
        if (_setDiff(_images, _original?.images ?? const [])) {
          patch['images'] = _images;
        }
        if (_isVerified != _original?.isVerified) {
          patch['is_verified'] = _isVerified;
        }
        // P0 任务 1：source_url 编辑
        final newSourceUrl = _sourceUrlCtl.text.trim().isEmpty
            ? null
            : _sourceUrlCtl.text.trim();
        final origSourceUrl = (_original?.sourceUrl ?? '').trim().isEmpty
            ? null
            : _original!.sourceUrl;
        if (newSourceUrl != origSourceUrl) {
          patch['source_url'] = newSourceUrl;
        }
        if (patch.isNotEmpty) {
          await ref.read(propertyServiceProvider)
              .updateProperty(widget.propertyId!, patch);
        }
        _toast('已保存');
      } else {
        // 创建
        await ref.read(propertyServiceProvider).createProperty(
              community: _communityCtl.text.trim(),
              layout: _layout,
              area: double.parse(_areaCtl.text),
              totalPrice: double.parse(_priceCtl.text) * 10000,
              tags: _tags.toList(),
              images: _images,
              viewingTime: _viewingTime,
              isVerified: _isVerified,
              sourceUrl: _sourceUrlCtl.text.trim().isEmpty
                  ? null
                  : _sourceUrlCtl.text.trim(),
            );
        _toast('已发布');
      }
      if (mounted) context.pop();
    } catch (e) {
      setState(() {
        _error = '${_isEdit ? "保存" : "发布"}失败: $e';
        _submitting = false;
      });
    }
  }

  bool _setDiff(List<String> a, List<String> b) =>
      a.length != b.length || !a.asMap().entries.every((e) => e.value == b[e.key]);
  bool _tagsSetDiff(Set<String> a, Set<String> b) =>
      a.length != b.length || !a.containsAll(b);

  // ============================================================
  //  UI
  // ============================================================

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme;
    final isEditLoading = _isEdit && !_prefilled;

    return Scaffold(
      appBar: AppBar(
        title: Text(_isEdit ? '编辑房源' : '发布房源'),
        actions: [
          if (isEditLoading)
            const Padding(
              padding: EdgeInsets.all(16),
              child: SizedBox(
                width: 18, height: 18,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
        ],
      ),
      body: isEditLoading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // ====== 图片区 ======
                    _buildImageSection(color),
                    const SizedBox(height: 16),

                    // ====== P0 任务 1：贝壳链接粘贴入口 ======
                    // 仅创建模式显示；编辑模式 source_url 一般不变
                    if (!_isEdit) ...[
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
                    ],

                    // ====== 基础信息 ======
                    TextFormField(
                      controller: _communityCtl,
                      decoration: const InputDecoration(
                        labelText: '小区名',
                        hintText: '如：望京西园',
                        prefixIcon: Icon(Icons.location_city),
                      ),
                      validator: (v) =>
                          (v == null || v.isEmpty) ? '请输入小区名' : null,
                    ),
                    const SizedBox(height: 16),
                    DropdownButtonFormField<String>(
                      initialValue: _layout,
                      decoration: const InputDecoration(labelText: '户型'),
                      items: kLayoutOptions
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
                            validator: (v) =>
                                (v == null || v.isEmpty) ? '必填' : null,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _priceCtl,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(labelText: '总价（万）'),
                            validator: (v) =>
                                (v == null || v.isEmpty) ? '必填' : null,
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
                      Text(_error!, style: TextStyle(color: color.error)),
                    ],
                    const SizedBox(height: 32),
                    FilledButton(
                      onPressed: _submitting ? null : _submit,
                      child: _submitting
                          ? const SizedBox(
                              width: 20, height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Text(_isEdit ? '保存修改' : '发布'),
                    ),
                  ],
                ),
              ),
            ),
    );
  }

  // ============================================================
  //  图片区块
  // ============================================================

  Widget _buildImageSection(ColorScheme color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.image_outlined, size: 18),
            const SizedBox(width: 6),
            const Text('房源图片', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
            const SizedBox(width: 6),
            Text(
              '${_images.length}/9',
              style: TextStyle(fontSize: 12, color: color.onSurface.withValues(alpha: 0.5)),
            ),
          ],
        ),
        const SizedBox(height: 8),
        // 缩略图网格
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            // 上传中 placeholder
            for (final _ in _uploading)
              SizedBox(
                width: 90, height: 90,
                child: Container(
                  decoration: BoxDecoration(
                    color: color.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Center(
                    child: SizedBox(
                      width: 24, height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  ),
                ),
              ),
            // 已上传图
            for (var i = 0; i < _images.length; i++) _buildImageTile(i, color),
            // 添加按钮
            if (_images.length < 9) _buildAddButton(color),
          ],
        ),
      ],
    );
  }

  Widget _buildImageTile(int index, ColorScheme color) {
    final url = _images[index];
    return SizedBox(
      width: 90, height: 90,
      child: Stack(
        children: [
          Positioned.fill(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: url.startsWith('http')
                  ? CachedNetworkImage(
                      imageUrl: url,
                      fit: BoxFit.cover,
                      placeholder: (_, __) => Container(color: color.surfaceContainerHighest),
                      errorWidget: (_, __, ___) => Container(
                        color: color.surfaceContainerHighest,
                        child: const Icon(Icons.broken_image, color: Colors.grey),
                      ),
                    )
                  : Container(
                      color: color.surfaceContainerHighest,
                      child: const Icon(Icons.image),
                    ),
            ),
          ),
          // 序号徽章
          if (index == 0)
            Positioned(
              top: 2, left: 2,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                decoration: BoxDecoration(
                  color: color.primary,
                  borderRadius: BorderRadius.circular(3),
                ),
                child: const Text('封面', style: TextStyle(color: Colors.white, fontSize: 9)),
              ),
            ),
          // 删除按钮
          Positioned(
            top: 0, right: 0,
            child: GestureDetector(
              onTap: () => _removeImage(index),
              child: Container(
                decoration: const BoxDecoration(
                  color: Colors.black54,
                  shape: BoxShape.circle,
                ),
                padding: const EdgeInsets.all(3),
                child: const Icon(Icons.close, color: Colors.white, size: 14),
              ),
            ),
          ),
          // 重排序（长按拖拽，MVP 用左右按钮）
          if (_images.length > 1)
            Positioned(
              bottom: 0, left: 0, right: 0,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  if (index > 0)
                    InkWell(
                      onTap: () => _moveImage(index, index - 1),
                      child: Container(
                        color: Colors.black54,
                        padding: const EdgeInsets.all(2),
                        child: const Icon(Icons.chevron_left, color: Colors.white, size: 14),
                      ),
                    )
                  else
                    const SizedBox(width: 18),
                  if (index < _images.length - 1)
                    InkWell(
                      onTap: () => _moveImage(index, index + 1),
                      child: Container(
                        color: Colors.black54,
                        padding: const EdgeInsets.all(2),
                        child: const Icon(Icons.chevron_right, color: Colors.white, size: 14),
                      ),
                    )
                  else
                    const SizedBox(width: 18),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildAddButton(ColorScheme color) {
    return SizedBox(
      width: 90, height: 90,
      child: PopupMenuButton<String>(
        tooltip: '添加图片',
        onSelected: (v) {
          if (v == 'gallery') {
            _pickAndUpload(source: ImageSource.gallery);
          } else if (v == 'camera') {
            _pickAndUpload(source: ImageSource.camera);
          }
        },
        itemBuilder: (_) => const [
          PopupMenuItem(
            value: 'gallery',
            child: Row(children: [Icon(Icons.photo_library_outlined, size: 18), SizedBox(width: 8), Text('从相册')]),
          ),
          PopupMenuItem(
            value: 'camera',
            child: Row(children: [Icon(Icons.camera_alt_outlined, size: 18), SizedBox(width: 8), Text('拍照')]),
          ),
        ],
        child: Container(
          decoration: BoxDecoration(
            color: color.surfaceContainerHighest.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.outline.withValues(alpha: 0.3), style: BorderStyle.solid),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.add_a_photo_outlined, color: color.onSurface.withValues(alpha: 0.6)),
              const SizedBox(height: 2),
              Text('添加', style: TextStyle(fontSize: 11, color: color.onSurface.withValues(alpha: 0.6))),
            ],
          ),
        ),
      ),
    );
  }
}
