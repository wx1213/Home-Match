/// API 响应包装
class ApiResponse<T> {
  final int code;
  final String message;
  final T? data;

  const ApiResponse({
    required this.code,
    required this.message,
    this.data,
  });

  bool get isOk => code == 0;

  factory ApiResponse.fromJson(
    Map<String, dynamic> json,
    T Function(dynamic) parse,
  ) {
    return ApiResponse(
      code: json['code'] as int? ?? -1,
      message: json['message'] as String? ?? '',
      data: json['data'] == null ? null : parse(json['data']),
    );
  }
}

/// API 错误（友好提示）
class ApiException implements Exception {
  final int code;
  final String message;
  final int? httpStatus;

  const ApiException({
    required this.code,
    required this.message,
    this.httpStatus,
  });

  @override
  String toString() => '[$code] $message';
}
