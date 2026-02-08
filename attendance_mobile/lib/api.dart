import 'dart:convert';
import 'dart:typed_data';

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';

const String baseUrl = 'https://att.connectingpoint.in';

class Session {
  int? id;
  String? name;
  String? mobile;
  String? companyName;
  String? profilePhoto;
  bool vehicleLog = false;
  bool manager = false;
  bool shopManager = false;

  bool get loggedIn => id != null;
}

final session = Session();

class ApiClient {
  final Dio _dio;
  ApiClient._(this._dio);

  static ApiClient? _instance;

  static ApiClient get instance {
    _instance ??= ApiClient._(_buildDio());
    return _instance!;
  }

  static Dio _buildDio() {
    final dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
      ),
    );
    final jar = CookieJar();
    dio.interceptors.add(CookieManager(jar));
    return dio;
  }

  Future<void> login({
    required String mobile,
    required String password,
    String? companyCode,
  }) async {
    final res = await _dio.post(
      '/api/login',
      data: {
        'mobile': mobile,
        'password': password,
        'company_code': companyCode ?? '',
      },
    );
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Login failed');
    }
    final emp = res.data['employee'];
    session.id = emp['id'];
    session.name = emp['name'];
    session.mobile = emp['mobile'];
    session.companyName = emp['company_name'];
    session.profilePhoto = emp['profile_photo'];
    session.vehicleLog = emp['vehicle_log_enabled'] == true;
    session.manager = emp['manager_role'] == true;
    session.shopManager = emp['shop_manager_role'] == true;
  }

  Future<Map<String, dynamic>> me() async {
    final res = await _dio.get('/api/me');
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Not logged in');
    }
    return Map<String, dynamic>.from(res.data['employee']);
  }

  Future<void> submitAttendance({
    required String action,
    required List<Uint8List> photos,
    required double lat,
    required double lon,
    String subject = '',
  }) async {
    final photoBase64 = photos.map((p) => base64Encode(p)).toList();
    final res = await _dio.post(
      '/api/attendance',
      data: {
        'action': action,
        'photos': photoBase64,
        'location': {'latitude': lat, 'longitude': lon},
        'subject': subject,
      },
    );
    if (res.data['status'] != 'success') {
      throw Exception(res.data['message'] ?? 'Attendance failed');
    }
  }

  Future<List<Map<String, dynamic>>> myWork() async {
    final res = await _dio.get('/api/my-work');
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Failed');
    }
    final list = (res.data['works'] as List).cast<Map<String, dynamic>>();
    return list;
  }

  Future<Map<String, dynamic>> workDetail(int id) async {
    final res = await _dio.get('/api/work/$id');
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Failed');
    }
    return Map<String, dynamic>.from(res.data['work']);
  }

  Future<void> workCheckin({
    required int workId,
    required double lat,
    required double lon,
  }) async {
    final res = await _dio.post(
      '/api/work/checkin',
      data: {'work_id': workId, 'lat': lat, 'lon': lon},
    );
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Check-in failed');
    }
  }

  Future<void> workCheckout({
    required int workId,
    required double lat,
    required double lon,
    required Uint8List photoBytes,
    String? amount,
    String? paymentMethod,
  }) async {
    final form = FormData.fromMap({
      'work_id': workId,
      'lat': lat,
      'lon': lon,
      'amount': amount ?? '',
      'payment_method': paymentMethod ?? 'cash',
      'photo': MultipartFile.fromBytes(photoBytes, filename: 'checkout.jpg'),
    });
    final res = await _dio.post('/api/work/checkout', data: form);
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Check-out failed');
    }
  }

  Future<List<Map<String, dynamic>>> employees() async {
    final res = await _dio.get('/api/employees');
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Failed');
    }
    final list = (res.data['employees'] as List).cast<Map<String, dynamic>>();
    return list;
  }

  Future<void> assignWork(Map<String, dynamic> payload) async {
    final res = await _dio.post('/api/work-assign', data: payload);
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Assign failed');
    }
  }

  Future<List<Map<String, dynamic>>> workRecords() async {
    final res = await _dio.get('/api/work-records');
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Failed');
    }
    final list = (res.data['records'] as List).cast<Map<String, dynamic>>();
    return list;
  }

  Future<List<Map<String, dynamic>>> attendanceRecords() async {
    final res = await _dio.get('/api/attendance-records');
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Failed');
    }
    final list = (res.data['records'] as List).cast<Map<String, dynamic>>();
    return list;
  }

  Future<List<Map<String, dynamic>>> expenses() async {
    final res = await _dio.get('/api/expenses');
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Failed');
    }
    final list = (res.data['expenses'] as List).cast<Map<String, dynamic>>();
    return list;
  }

  Future<void> submitExpense({
    required String title,
    required String amount,
    required String expenseDate,
    required String description,
    Uint8List? photoBytes,
  }) async {
    final form = FormData.fromMap({
      'title': title,
      'amount': amount,
      'expense_date': expenseDate,
      'description': description,
      if (photoBytes != null)
        'photo': MultipartFile.fromBytes(photoBytes, filename: 'bill.jpg'),
    });
    final res = await _dio.post('/api/expenses', data: form);
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Expense submit failed');
    }
  }

  Future<List<Map<String, dynamic>>> advances() async {
    final res = await _dio.get('/api/advance');
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Failed');
    }
    final list = (res.data['requests'] as List).cast<Map<String, dynamic>>();
    return list;
  }

  Future<void> requestAdvance({
    required String amount,
    required String reason,
  }) async {
    final res = await _dio.post(
      '/api/advance',
      data: {'amount': amount, 'reason': reason},
    );
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Advance request failed');
    }
  }

  Future<void> uploadProfilePhoto(Uint8List photoBytes) async {
    final formData = FormData.fromMap({
      'photo': MultipartFile.fromBytes(photoBytes, filename: 'profile.jpg'),
    });
    final res = await _dio.post('/api/upload-profile-photo', data: formData);
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Photo upload failed');
    }
  }

  Future<void> updateLiveLocation({
    required double latitude,
    required double longitude,
    double? accuracy,
  }) async {
    final res = await _dio.post(
      '/api/update_live_location',
      data: {
        'latitude': latitude,
        'longitude': longitude,
        'accuracy': accuracy,
      },
    );
    if (res.data['status'] != 'ok') {
      throw Exception(res.data['message'] ?? 'Location update failed');
    }
  }
}
