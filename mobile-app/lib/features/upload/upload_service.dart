/// 上传服务 - 封装 dio multipart 上传 + 压缩
library;

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_image_compress/flutter_image_compress.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/network/dio_client.dart';

/// 上传结果
class UploadResult {
  final String url;
  final String filename;
  final int size;
  final String contentType;

  const UploadResult({
    required this.url,
    required this.filename,
    required this.size,
    required this.contentType,
  });

  factory UploadResult.fromJson(Map<String, dynamic> json) => UploadResult(
        url: json['url'] as String,
        filename: json['filename'] as String,
        size: json['size'] as int,
        contentType: json['content_type'] as String,
      );
}

class UploadService {
  final Dio _dio;
  final ImagePicker _picker = ImagePicker();

  UploadService(this._dio);

  /// 选图（相册多选 / 拍照）
  /// [maxImages] 最多选几张（仅相册有效）
  /// [source] gallery（默认）/ camera
  Future<List<XFile>> pickImages({
    int? maxImages,
    ImageSource source = ImageSource.gallery,
  }) async {
    if (source == ImageSource.camera) {
      final f = await _picker.pickImage(source: ImageSource.camera);
      return f != null ? [f] : [];
    }
    if (maxImages == 1) {
      final f = await _picker.pickImage(source: ImageSource.gallery);
      return f != null ? [f] : [];
    }
    return await _picker.pickMultiImage(limit: maxImages);
  }

  /// 压缩图片（P0：单边最长 1600px，质量 80%）
  /// - 避免大图上传失败 / 太慢
  /// - 单图压后通常 < 1MB
  /// - 返 (bytes, filename) 元组：直接给 MultipartFile.fromBytes 用
  Future<(Uint8List, String)> compress(
    XFile file, {
    int maxWidth = 1600,
    int quality = 80,
  }) async {
    final filename = file.name.replaceAll(RegExp(r'\.\w+$'), '.jpg');
    try {
      final bytes = await file.readAsBytes();
      final result = await FlutterImageCompress.compressWithList(
        bytes,
        minWidth: maxWidth,
        minHeight: maxWidth,
        quality: quality,
        format: CompressFormat.jpeg,
      );
      return (result, filename);
    } catch (e) {
      // 压缩失败：返回原图
      debugPrint('[upload] compress failed: $e, using original');
      final bytes = await file.readAsBytes();
      return (bytes, filename);
    }
  }

  /// 单张上传（multipart）
  Future<UploadResult> uploadOne(XFile file) async {
    final (bytes, filename) = await compress(file);
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        bytes,
        filename: filename,
      ),
    });
    final resp = await _dio.post('/v1/upload/image', data: formData);
    final data = resp.data['data'] as Map<String, dynamic>;
    return UploadResult.fromJson(data);
  }

  /// 批量上传（并发 3）
  Future<List<UploadResult>> uploadMany(List<XFile> files) async {
    if (files.isEmpty) return [];
    if (files.length == 1) return [await uploadOne(files.first)];

    // 压缩所有
    final compressed = await Future.wait(files.map((f) => compress(f)));

    // 构造 multipart（用 fromBytes 避免 XFile.fromData 路径不存在问题）
    final formData = FormData.fromMap({});
    for (final (bytes, filename) in compressed) {
      formData.files.add(MapEntry(
        'files',
        MultipartFile.fromBytes(bytes, filename: filename),
      ));
    }

    final resp = await _dio.post('/v1/upload/images', data: formData);
    final data = (resp.data['data'] as List).cast<Map<String, dynamic>>();
    return data.map(UploadResult.fromJson).toList();
  }
}

final uploadServiceProvider = Provider<UploadService>((ref) {
  return UploadService(ref.read(dioProvider));
});
