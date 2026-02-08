import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:image_cropper/image_cropper.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:dio/dio.dart';

import 'api.dart';

const String kBackgroundImage = 'assets/images/background.png';
const String kPrivacyUrl = 'https://att.connectingpoint.in/privacy';

class SoundHelper {
  static final AudioPlayer _player = AudioPlayer();

  static Future<void> playSuccess() async {
    try {
      await _player.play(AssetSource('sounds/success.mp3'));
    } catch (e) {
      print('Error playing success sound: $e');
    }
  }

  static Future<void> playFailure() async {
    try {
      await _player.play(AssetSource('sounds/failure.mp3'));
    } catch (e) {
      print('Error playing failure sound: $e');
    }
  }
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

class AppPrefs {
  static const _kCompany = 'company_code';
  static const _kMobile = 'mobile';
  static const _kPassword = 'password';

  static Future<SharedPreferences> _prefs() => SharedPreferences.getInstance();

  static Future<void> saveCredentials({
    required String company,
    required String mobile,
    required String password,
  }) async {
    final p = await _prefs();
    await p.setString(_kCompany, company);
    await p.setString(_kMobile, mobile);
    await p.setString(_kPassword, password);
  }

  static Future<Map<String, String>?> readCredentials() async {
    final p = await _prefs();
    final company = p.getString(_kCompany);
    final mobile = p.getString(_kMobile);
    final password = p.getString(_kPassword);
    if (mobile == null || password == null) return null;
    return {'company': company ?? '', 'mobile': mobile, 'password': password};
  }
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Attendance Mobile',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueGrey),
        useMaterial3: true,
        textTheme: const TextTheme(
          bodyLarge: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w500,
            color: Colors.black87,
          ),
          bodyMedium: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w400,
            color: Colors.black87,
          ),
          titleLarge: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: Colors.black87,
          ),
          titleMedium: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: Colors.black87,
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: Colors.grey.shade400),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide(color: Colors.grey.shade400),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: const BorderSide(color: Colors.blueGrey, width: 2),
          ),
          labelStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w500,
            color: Colors.black87,
          ),
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            textStyle: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
            padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 24),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
      ),
      home: const StartupPage(),
    );
  }
}

class StartupPage extends StatefulWidget {
  const StartupPage({super.key});

  @override
  State<StartupPage> createState() => _StartupPageState();
}

class _StartupPageState extends State<StartupPage> {
  String? _error;
  bool _loading = true;

  Future<void> _autoLogin() async {
    final creds = await AppPrefs.readCredentials();
    if (creds == null) {
      setState(() => _loading = false);
      return;
    }
    try {
      await ApiClient.instance.login(
        mobile: creds['mobile']!,
        password: creds['password']!,
        companyCode: creds['company']!,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const AttendancePage()),
      );
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  void initState() {
    super.initState();
    _autoLogin();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return LoginPage(errorOverride: _error);
  }
}

class LoginPage extends StatefulWidget {
  final String? errorOverride;
  const LoginPage({super.key, this.errorOverride});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _mobile = TextEditingController();
  final _password = TextEditingController();
  final _company = TextEditingController();
  bool _loading = false;
  String? _error;

  Future<void> _login() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ApiClient.instance.login(
        mobile: _mobile.text.trim(),
        password: _password.text,
        companyCode: _company.text.trim(),
      );
      await AppPrefs.saveCredentials(
        company: _company.text.trim(),
        mobile: _mobile.text.trim(),
        password: _password.text,
      );
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const AttendancePage()),
      );
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error == null && widget.errorOverride != null) {
      _error = widget.errorOverride;
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('Employee Login'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.of(
              context,
            ).push(MaterialPageRoute(builder: (_) => const SetupPage())),
          ),
        ],
      ),
      body: AppBackground(
        child: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const SizedBox(height: 8),
                  TextField(
                    controller: _company,
                    decoration: const InputDecoration(
                      labelText: 'Company Code (optional)',
                    ),
                  ),
                  TextField(
                    controller: _mobile,
                    decoration: const InputDecoration(labelText: 'Mobile'),
                  ),
                  TextField(
                    controller: _password,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: 'Password'),
                  ),
                  const SizedBox(height: 16),
                  if (_error != null)
                    Text(_error!, style: const TextStyle(color: Colors.red)),
                  ElevatedButton(
                    onPressed: _loading ? null : _login,
                    child: _loading
                        ? const CircularProgressIndicator()
                        : const Text('Login'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Welcome, ${session.name ?? ''}')),
      drawer: const AppDrawer(current: AppMenu.attendance),
      body: AppBackground(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Hello, ${session.name ?? ''}',
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                const Text('Use the left menu to open pages.'),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _navButton(BuildContext context, String label, Widget page) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: ElevatedButton(
        onPressed: () =>
            Navigator.of(context).push(MaterialPageRoute(builder: (_) => page)),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 14),
          child: Text(label),
        ),
      ),
    );
  }
}

class AttendancePage extends StatefulWidget {
  const AttendancePage({super.key});

  @override
  State<AttendancePage> createState() => _AttendancePageState();
}

class _AttendancePageState extends State<AttendancePage> {
  final ImagePicker _picker = ImagePicker();
  final List<Uint8List> _photos = [];
  final _subject = TextEditingController();
  Position? _pos;
  String _action = 'in';
  String? _msg;
  bool _loading = false;
  DateTime? _cooldownEnd;
  String _currentDate = '';
  XFile? _cameraPreview;
  Timer? _timer;
  Timer? _locationTimer;
  String _companyName = '';
  CameraController? _cameraController;
  List<CameraDescription>? _cameras;
  bool _isCameraInitialized = false;

  @override
  void initState() {
    super.initState();
    _initializePage();
    _initializeCamera();
    _startTimer();
    _startLocationTracking();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _locationTimer?.cancel();
    _cameraController?.dispose();
    super.dispose();
  }

  Future<void> _initializeCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras!.isEmpty) return;

      // Find front camera, fallback to first available camera
      final frontCamera = _cameras!.firstWhere(
        (camera) => camera.lensDirection == CameraLensDirection.front,
        orElse: () => _cameras!.first,
      );

      _cameraController = CameraController(
        frontCamera,
        ResolutionPreset.medium,
        enableAudio: false,
      );

      await _cameraController!.initialize();

      if (mounted) {
        setState(() {
          _isCameraInitialized = true;
        });
      }
    } catch (e) {
      print('Error initializing camera: $e');
    }
  }

  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (mounted) {
        setState(() {
          _updateDate();
        });
      }
    });
  }

  void _startLocationTracking() {
    // Send location every 1 minute
    _locationTimer = Timer.periodic(const Duration(minutes: 1), (timer) async {
      if (!session.loggedIn) {
        timer.cancel();
        return;
      }

      try {
        final position = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.high,
        );

        await ApiClient.instance.updateLiveLocation(
          latitude: position.latitude,
          longitude: position.longitude,
          accuracy: position.accuracy,
        );
      } catch (e) {
        print('Error updating live location: $e');
      }
    });
  }

  Future<void> _initializePage() async {
    // Check and request permissions first
    await _checkPermissions();
    // Automatically get GPS and date
    await _getLocation();
    _updateDate();
    // Determine punch type automatically
    await _determinePunchType();
    // Load company name
    setState(() {
      _companyName = session.companyName ?? 'Company';
    });
  }

  Future<void> _checkPermissions() async {
    // Check GPS permission
    final locationPerm = await Geolocator.checkPermission();
    if (locationPerm == LocationPermission.denied ||
        locationPerm == LocationPermission.deniedForever) {
      if (mounted) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('GPS Permission Required'),
            content: const Text(
              'Please enable GPS/Location permission to use attendance feature.',
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.pop(context);
                  Geolocator.requestPermission();
                },
                child: const Text('Enable'),
              ),
            ],
          ),
        );
      }
    }
  }

  void _updateDate() {
    final now = DateTime.now();
    _currentDate =
        '${now.day}/${now.month}/${now.year} ${now.hour}:${now.minute.toString().padLeft(2, '0')}:${now.second.toString().padLeft(2, '0')}';
  }

  Future<void> _determinePunchType() async {
    // Check cooldown from SharedPreferences
    final prefs = await SharedPreferences.getInstance();
    final lastPunchTime = prefs.getString('last_punch_time');
    final lastAction = prefs.getString('last_action') ?? 'out';

    if (lastPunchTime != null) {
      final lastPunch = DateTime.parse(lastPunchTime);
      final now = DateTime.now();
      final difference = now.difference(lastPunch);

      if (difference.inHours < 1) {
        // Still in cooldown
        setState(() {
          _cooldownEnd = lastPunch.add(const Duration(hours: 1));
        });
        return;
      }
    }

    // Auto-determine: if last was 'out' or null, next is 'in', otherwise 'out'
    setState(() {
      _action = lastAction == 'out' ? 'in' : 'out';
    });
  }

  Future<void> _getLocation() async {
    final perm = await Geolocator.requestPermission();
    if (perm == LocationPermission.denied ||
        perm == LocationPermission.deniedForever) {
      setState(() => _msg = 'Location permission denied');
      return;
    }
    try {
      final pos = await Geolocator.getCurrentPosition();
      setState(() => _pos = pos);
    } catch (e) {
      setState(() => _msg = 'Failed to get GPS: $e');
    }
  }

  Future<void> _takePhoto() async {
    try {
      if (_cameraController != null && _cameraController!.value.isInitialized) {
        // Take photo from live camera preview
        final XFile photo = await _cameraController!.takePicture();
        final bytes = await photo.readAsBytes();
        if (mounted) {
          setState(() {
            _photos.add(bytes);
            _cameraPreview = photo;
          });
        }
      } else {
        // Fallback to image picker if camera not initialized
        final file = await _picker.pickImage(
          source: ImageSource.camera,
          imageQuality: 75,
        );
        if (file == null) return;
        final bytes = await file.readAsBytes();
        if (mounted) {
          setState(() {
            _photos.add(bytes);
            _cameraPreview = file;
          });
        }
      }
    } catch (e) {
      print('Error taking photo: $e');
    }
  }

  Future<void> _submit() async {
    // Check cooldown - TEMPORARILY DISABLED FOR TESTING
    // if (_cooldownEnd != null && DateTime.now().isBefore(_cooldownEnd!)) {
    //   final remaining = _cooldownEnd!.difference(DateTime.now());
    //   setState(() => _msg = 'Please wait ${remaining.inMinutes} more minutes');
    //   return;
    // }

    if (_pos == null) {
      await _getLocation();
    }
    if (_pos == null || _photos.isEmpty) {
      setState(() => _msg = 'GPS and photo required');
      return;
    }
    setState(() {
      _loading = true;
      _msg = null;
    });
    try {
      await ApiClient.instance.submitAttendance(
        action: _action,
        photos: _photos,
        lat: _pos!.latitude,
        lon: _pos!.longitude,
        subject: _subject.text.trim(),
      );

      // Save punch time and action for cooldown
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        'last_punch_time',
        DateTime.now().toIso8601String(),
      );
      await prefs.setString('last_action', _action);

      // Update to next punch type
      final nextAction = _action == 'in' ? 'out' : 'in';
      setState(() {
        _cooldownEnd = DateTime.now().add(const Duration(hours: 1));
        _action = nextAction;
        _photos.clear();
        _cameraPreview = null;
      });

      // Show success popup
      if (mounted) {
        SoundHelper.playSuccess();
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Success'),
            content: Text(
              '${_action == 'in' ? 'Punch In' : 'Punch Out'} submitted successfully!',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('OK'),
              ),
            ],
          ),
        );
      }

      setState(() => _msg = 'Attendance submitted successfully');
    } catch (e) {
      SoundHelper.playFailure();
      setState(() => _msg = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  String _getCooldownText() {
    if (_cooldownEnd == null) return '';
    final now = DateTime.now();
    if (now.isAfter(_cooldownEnd!)) return '';
    final remaining = _cooldownEnd!.difference(now);
    final minutes = remaining.inMinutes;
    final seconds = remaining.inSeconds % 60;
    return 'Cooldown: ${minutes}m ${seconds}s';
  }

  @override
  Widget build(BuildContext context) {
    // Temporarily disable cooldown for testing
    final isCooldown = false;
    // final isCooldown =
    //     _cooldownEnd != null && DateTime.now().isBefore(_cooldownEnd!);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Attendance'),
        actions: [
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: CircleAvatar(
              backgroundColor: Colors.grey.shade300,
              child: Text(
                session.name?.substring(0, 1).toUpperCase() ?? 'U',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          ),
        ],
      ),
      drawer: const AppDrawer(current: AppMenu.attendance),
      bottomNavigationBar: Container(
        padding: const EdgeInsets.all(12),
        color: Colors.black87,
        child: Text(
          _companyName,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 14,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      body: AppBackground(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Date and Time
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.9),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _currentDate,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 8),

              // Auto-determined action with GPS
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: _action == 'in'
                      ? Colors.green.shade100
                      : Colors.red.shade100,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  children: [
                    Text(
                      _action == 'in' ? 'PUNCH IN' : 'PUNCH OUT',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: _action == 'in'
                            ? Colors.green.shade700
                            : Colors.red.shade700,
                      ),
                    ),
                    if (_pos != null)
                      Text(
                        'GPS: ${_pos!.latitude.toStringAsFixed(4)}, ${_pos!.longitude.toStringAsFixed(4)}',
                        style: const TextStyle(fontSize: 10),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 8),

              // Live Camera Preview
              Expanded(
                child: Stack(
                  children: [
                    Container(
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.black,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: _isCameraInitialized && _cameraController != null
                            ? CameraPreview(_cameraController!)
                            : Center(
                                child: Icon(
                                  Icons.camera_alt,
                                  size: 64,
                                  color: Colors.white.withOpacity(0.3),
                                ),
                              ),
                      ),
                    ),
                    if (_photos.isNotEmpty)
                      Positioned(
                        top: 8,
                        right: 8,
                        child: Container(
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.white, width: 2),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(6),
                            child: Image.memory(
                              _photos.last,
                              width: 80,
                              height: 80,
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                      ),
                    if (_photos.isNotEmpty)
                      Positioned(
                        bottom: 8,
                        left: 8,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(0.7),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            'Photos: ${_photos.length}',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 8),

              // Take Photo Button
              ElevatedButton.icon(
                onPressed: isCooldown ? null : _takePhoto,
                icon: const Icon(Icons.camera_alt, size: 18),
                label: const Text('Take Photo'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
              ),
              const SizedBox(height: 8),

              // Cooldown timer and Submit Button
              if (isCooldown)
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.orange.shade100,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    _getCooldownText(),
                    style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: Colors.orange.shade700,
                    ),
                    textAlign: TextAlign.center,
                  ),
                )
              else
                ElevatedButton(
                  onPressed: _loading ? null : _submit,
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.all(12),
                    backgroundColor: _action == 'in'
                        ? Colors.green
                        : Colors.red,
                  ),
                  child: _loading
                      ? const CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 2,
                        )
                      : Text(
                          'Submit ${_action == 'in' ? 'Punch In' : 'Punch Out'}',
                          style: const TextStyle(
                            fontSize: 16,
                            color: Colors.white,
                          ),
                        ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class MyWorkPage extends StatefulWidget {
  const MyWorkPage({super.key});

  @override
  State<MyWorkPage> createState() => _MyWorkPageState();
}

class _MyWorkPageState extends State<MyWorkPage> {
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiClient.instance.myWork();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Work')),
      drawer: const AppDrawer(current: AppMenu.myWork),
      body: AppBackground(
        child: FutureBuilder(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return Center(child: Text(snapshot.error.toString()));
            }
            final list = snapshot.data as List<Map<String, dynamic>>;
            return ListView.builder(
              itemCount: list.length,
              itemBuilder: (context, i) {
                final w = list[i];
                return ListTile(
                  title: Text(w['customer_name'] ?? ''),
                  subtitle: Text(w['service_type'] ?? ''),
                  trailing: Text(w['status'] ?? ''),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => WorkDetailPage(workId: w['id']),
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class WorkDetailPage extends StatefulWidget {
  final int workId;
  const WorkDetailPage({super.key, required this.workId});

  @override
  State<WorkDetailPage> createState() => _WorkDetailPageState();
}

class _WorkDetailPageState extends State<WorkDetailPage> {
  Map<String, dynamic>? _work;
  final _amount = TextEditingController();
  final _notes = TextEditingController();
  final ImagePicker _picker = ImagePicker();
  Uint8List? _photo;
  Position? _pos;
  String? _msg;
  String _paymentMethod = 'cash'; // 'cash' or 'upi'
  bool _showPayNow = false;
  String _selectedStatus = 'in_progress';

  Future<void> _load() async {
    final w = await ApiClient.instance.workDetail(widget.workId);
    setState(() => _work = w);
  }

  Future<void> _gps() async {
    final perm = await Geolocator.requestPermission();
    if (perm == LocationPermission.denied ||
        perm == LocationPermission.deniedForever) {
      setState(() => _msg = 'Location permission denied');
      return;
    }
    _pos = await Geolocator.getCurrentPosition();
  }

  Future<void> _pickPhoto() async {
    final file = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 75,
    );
    if (file == null) return;
    _photo = await file.readAsBytes();
    setState(() {});
  }

  Future<void> _checkin() async {
    await _gps();
    if (_pos == null) return;
    await ApiClient.instance.workCheckin(
      workId: widget.workId,
      lat: _pos!.latitude,
      lon: _pos!.longitude,
    );
    await _load();
  }

  Future<void> _checkout() async {
    await _gps();
    if (_pos == null) return;
    if (_photo == null) {
      setState(() => _msg = 'Photo required');
      return;
    }
    await ApiClient.instance.workCheckout(
      workId: widget.workId,
      lat: _pos!.latitude,
      lon: _pos!.longitude,
      photoBytes: _photo!,
      amount: _amount.text.trim(),
      paymentMethod: _paymentMethod,
    );
    SoundHelper.playSuccess();
    await _load();
  }

  void _showUpiQR() {
    final amount = _amount.text.trim();
    if (amount.isEmpty) {
      setState(() => _msg = 'Please enter amount first');
      return;
    }

    final w = _work;
    final customerName = w?['customer_name'] ?? 'Customer';
    final serviceType = w?['service_type'] ?? 'Service';
    final upiString =
        'upi://pay?pa=connectingpoint@icici&pn=Connecting Point&am=$amount&cu=INR&tn=$serviceType for $customerName';

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Colors.white,
        title: const Text(
          'Customer Payment',
          style: TextStyle(fontWeight: FontWeight.bold, color: Colors.black87),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Ask customer to scan this QR code',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.black87,
                ),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.grey.shade300, width: 2),
                ),
                child: QrImageView(
                  data: upiString,
                  version: QrVersions.auto,
                  size: 250.0,
                  backgroundColor: Colors.white,
                  foregroundColor: Colors.black,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                '₹$amount',
                style: const TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  color: Colors.green,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'UPI ID: connectingpoint@icici',
                style: TextStyle(fontSize: 14, color: Colors.black54),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              setState(() {
                _paymentMethod = 'upi';
                _showPayNow = false;
              });
            },
            child: const Text('Payment Received'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final w = _work;
    return Scaffold(
      appBar: AppBar(title: const Text('Work Detail')),
      body: AppBackground(
        child: w == null
            ? const Center(child: CircularProgressIndicator())
            : Padding(
                padding: const EdgeInsets.all(16),
                child: ListView(
                  children: [
                    Text('Customer: ${w['customer_name'] ?? ''}'),
                    Text('Service: ${w['service_type'] ?? ''}'),
                    Text('Status: ${w['status'] ?? ''}'),
                    const SizedBox(height: 12),
                    if (_msg != null)
                      Text(_msg!, style: const TextStyle(color: Colors.red)),
                    if (w['status'] == 'assigned')
                      ElevatedButton(
                        onPressed: _checkin,
                        child: const Text('Check In'),
                      ),
                    if (w['status'] == 'in_progress') ...[
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.9),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Work Status:',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                                color: Colors.black87,
                              ),
                            ),
                            const SizedBox(height: 8),
                            DropdownButton<String>(
                              value: _selectedStatus,
                              isExpanded: true,
                              items: const [
                                DropdownMenuItem(
                                  value: 'in_progress',
                                  child: Text('In Progress'),
                                ),
                                DropdownMenuItem(
                                  value: 'pending',
                                  child: Text('Pending'),
                                ),
                                DropdownMenuItem(
                                  value: 'hold',
                                  child: Text('Hold'),
                                ),
                              ],
                              onChanged: (value) {
                                setState(
                                  () =>
                                      _selectedStatus = value ?? 'in_progress',
                                );
                              },
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _notes,
                        maxLines: 3,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Notes',
                          labelStyle: TextStyle(color: Colors.white),
                          filled: true,
                          fillColor: Colors.black26,
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _amount,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Amount (₹)',
                          labelStyle: TextStyle(color: Colors.white),
                          filled: true,
                          fillColor: Colors.black26,
                        ),
                        keyboardType: TextInputType.number,
                        onChanged: (value) {
                          setState(() {
                            _showPayNow = value.isNotEmpty;
                            _paymentMethod = 'cash';
                          });
                        },
                      ),
                      const SizedBox(height: 12),
                      if (_showPayNow)
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.9),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            children: [
                              const Text(
                                'Payment Method:',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 16,
                                  color: Colors.black87,
                                ),
                              ),
                              const SizedBox(height: 8),
                              Row(
                                children: [
                                  Expanded(
                                    child: ElevatedButton.icon(
                                      onPressed: () {
                                        setState(() {
                                          _paymentMethod = 'cash';
                                        });
                                      },
                                      icon: Icon(
                                        _paymentMethod == 'cash'
                                            ? Icons.check_circle
                                            : Icons.money,
                                      ),
                                      label: const Text('Cash'),
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor:
                                            _paymentMethod == 'cash'
                                            ? Colors.green
                                            : Colors.grey,
                                        foregroundColor: Colors.white,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: ElevatedButton.icon(
                                      onPressed: _showUpiQR,
                                      icon: const Icon(Icons.qr_code),
                                      label: const Text('UPI QR'),
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor: _paymentMethod == 'upi'
                                            ? Colors.green
                                            : Colors.blue,
                                        foregroundColor: Colors.white,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              if (_paymentMethod == 'upi')
                                const Padding(
                                  padding: EdgeInsets.only(top: 8),
                                  child: Text(
                                    '✓ UPI Payment Confirmed',
                                    style: TextStyle(
                                      color: Colors.green,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _pickPhoto,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.orange,
                          foregroundColor: Colors.white,
                        ),
                        child: const Text('Capture Photo'),
                      ),
                      if (_photo != null)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 8),
                          child: Text(
                            '✓ Photo captured',
                            style: TextStyle(
                              color: Colors.green,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      const SizedBox(height: 12),
                      ElevatedButton(
                        onPressed: _checkout,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.green,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                        ),
                        child: Text(
                          'Check Out (${_paymentMethod.toUpperCase()})',
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
      ),
    );
  }
}

class WorkAssignPage extends StatefulWidget {
  const WorkAssignPage({super.key});

  @override
  State<WorkAssignPage> createState() => _WorkAssignPageState();
}

class _WorkAssignPageState extends State<WorkAssignPage> {
  List<Map<String, dynamic>> _employees = [];
  int? _assignedTo;
  final _customer = TextEditingController();
  final _mobile = TextEditingController();
  final _address = TextEditingController();
  final _location = TextEditingController();
  final _notes = TextEditingController();
  String _service = 'Installation';
  String? _msg;

  Future<void> _load() async {
    final list = await ApiClient.instance.employees();
    setState(() => _employees = list);
  }

  Future<void> _assign() async {
    if (_assignedTo == null) {
      SoundHelper.playFailure();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please select an employee')),
      );
      return;
    }

    try {
      final assignedToId = _assignedTo;

      await ApiClient.instance.assignWork({
        'assigned_to': assignedToId,
        'customer_name': _customer.text,
        'customer_mobile': _mobile.text,
        'customer_address': _address.text,
        'customer_location': _location.text,
        'service_type': _service,
        'notes': _notes.text,
      });

      // Get employee name before clearing
      final empName = _employees.firstWhere(
        (e) => e['id'] == assignedToId,
      )['name'];

      // Clear form
      setState(() {
        _assignedTo = null;
        _customer.clear();
        _mobile.clear();
        _address.clear();
        _location.clear();
        _notes.clear();
        _service = 'Installation';
      });

      // Success feedback with sound
      SoundHelper.playSuccess();
      if (mounted) {
        showDialog(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Success'),
            content: const Text('Work assigned successfully!'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('OK'),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      SoundHelper.playFailure();
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Work Assign',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.blueGrey,
        foregroundColor: Colors.white,
      ),
      drawer: const AppDrawer(current: AppMenu.assignWork),
      body: AppBackground(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: _assignedTo != null
                      ? Colors.blue.shade100
                      : Colors.white,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: _assignedTo != null
                        ? Colors.blue
                        : Colors.grey.shade400,
                    width: 2,
                  ),
                ),
                child: DropdownButton<int>(
                  value: _assignedTo,
                  hint: const Text(
                    'Select employee',
                    style: TextStyle(color: Colors.black54),
                  ),
                  isExpanded: true,
                  underline: const SizedBox(),
                  items: _employees
                      .map(
                        (e) => DropdownMenuItem<int>(
                          value: e['id'],
                          child: Text(
                            '${e['name']} (${e['mobile']})',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: (v) => setState(() => _assignedTo = v),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _customer,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
                decoration: const InputDecoration(
                  labelText: 'Customer Name',
                  labelStyle: TextStyle(color: Colors.white),
                  filled: true,
                  fillColor: Colors.black26,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _mobile,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
                decoration: const InputDecoration(
                  labelText: 'Customer Mobile',
                  labelStyle: TextStyle(color: Colors.white),
                  filled: true,
                  fillColor: Colors.black26,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _address,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
                decoration: const InputDecoration(
                  labelText: 'Address',
                  labelStyle: TextStyle(color: Colors.white),
                  filled: true,
                  fillColor: Colors.black26,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _location,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
                decoration: const InputDecoration(
                  labelText: 'Location',
                  labelStyle: TextStyle(color: Colors.white),
                  filled: true,
                  fillColor: Colors.black26,
                ),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: Colors.orange.shade100,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.orange, width: 2),
                ),
                child: DropdownButton<String>(
                  value: _service,
                  isExpanded: true,
                  underline: const SizedBox(),
                  items: const [
                    DropdownMenuItem(
                      value: 'Installation',
                      child: Text(
                        'Installation',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    DropdownMenuItem(
                      value: 'Demo',
                      child: Text(
                        'Demo',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    DropdownMenuItem(
                      value: 'Camera Services',
                      child: Text(
                        'Camera Services',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    DropdownMenuItem(
                      value: 'Computer Services',
                      child: Text(
                        'Computer Services',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    DropdownMenuItem(
                      value: 'Printer Services',
                      child: Text(
                        'Printer Services',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    DropdownMenuItem(
                      value: 'Network Installation',
                      child: Text(
                        'Network Installation',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    DropdownMenuItem(
                      value: 'Network Breakdown',
                      child: Text(
                        'Network Breakdown',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    DropdownMenuItem(
                      value: 'Other',
                      child: Text(
                        'Other',
                        style: TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                  ],
                  onChanged: (v) =>
                      setState(() => _service = v ?? 'Installation'),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _notes,
                maxLines: 3,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
                decoration: const InputDecoration(
                  labelText: 'Notes',
                  labelStyle: TextStyle(color: Colors.white),
                  filled: true,
                  fillColor: Colors.black26,
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: _assign,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  textStyle: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                child: const Text('Assign Work'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class AttendanceRecordsPage extends StatefulWidget {
  const AttendanceRecordsPage({super.key});

  @override
  State<AttendanceRecordsPage> createState() => _AttendanceRecordsPageState();
}

class _AttendanceRecordsPageState extends State<AttendanceRecordsPage> {
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiClient.instance.attendanceRecords();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('View Records')),
      drawer: const AppDrawer(current: AppMenu.records),
      body: AppBackground(
        child: FutureBuilder(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return Center(child: Text(snapshot.error.toString()));
            }
            final list = snapshot.data as List<Map<String, dynamic>>;

            // Filter to last 60 days
            final now = DateTime.now();
            final sixtyDaysAgo = now.subtract(const Duration(days: 60));
            final filteredList = list.where((r) {
              try {
                final timestamp = r['timestamp'] as String?;
                if (timestamp == null) return false;
                final date = DateTime.parse(timestamp.split(' ')[0]);
                return date.isAfter(sixtyDaysAgo);
              } catch (e) {
                return true; // Include if can't parse
              }
            }).toList();

            if (filteredList.isEmpty) {
              return const Center(
                child: Text('No records found (Last 60 days)'),
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(8),
              itemCount: filteredList.length,
              itemBuilder: (context, i) {
                final r = filteredList[i];
                final action = '${r['action'] ?? ''}'.toUpperCase();
                final photos = r['photos'] as List?;
                final hasPhoto = photos != null && photos.isNotEmpty;

                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  color: action == 'IN'
                      ? Colors.green.shade50
                      : Colors.red.shade50,
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        // Photo thumbnail
                        if (hasPhoto)
                          Container(
                            margin: const EdgeInsets.only(right: 12),
                            decoration: BoxDecoration(
                              border: Border.all(
                                color: action == 'IN'
                                    ? Colors.green
                                    : Colors.red,
                                width: 2,
                              ),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(6),
                              child: Image.network(
                                photos.first,
                                width: 60,
                                height: 60,
                                fit: BoxFit.cover,
                                errorBuilder: (context, error, stackTrace) {
                                  return Container(
                                    width: 60,
                                    height: 60,
                                    color: Colors.grey.shade300,
                                    child: const Icon(
                                      Icons.image_not_supported,
                                    ),
                                  );
                                },
                              ),
                            ),
                          ),
                        // Text content
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                action,
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  color: action == 'IN'
                                      ? Colors.green.shade700
                                      : Colors.red.shade700,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                r['timestamp'] ?? '',
                                style: const TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.black87,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                r['location'] ?? '',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey.shade700,
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class ExpensesPage extends StatefulWidget {
  const ExpensesPage({super.key});

  @override
  State<ExpensesPage> createState() => _ExpensesPageState();
}

class _ExpensesPageState extends State<ExpensesPage> {
  final _title = TextEditingController();
  final _amount = TextEditingController();
  final _date = TextEditingController();
  final _desc = TextEditingController();
  final ImagePicker _picker = ImagePicker();
  Uint8List? _photo;
  String? _msg;
  bool _loading = false;
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _date.text = DateTime.now().toString().split(' ').first;
    _future = ApiClient.instance.expenses();
  }

  Future<void> _pickPhoto() async {
    final file = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 75,
    );
    if (file == null) return;
    _photo = await file.readAsBytes();
    setState(() {});
  }

  Future<void> _submit() async {
    setState(() {
      _loading = true;
      _msg = null;
    });
    try {
      await ApiClient.instance.submitExpense(
        title: _title.text.trim(),
        amount: _amount.text.trim(),
        expenseDate: _date.text.trim(),
        description: _desc.text.trim(),
        photoBytes: _photo,
      );
      SoundHelper.playSuccess();
      setState(() {
        _msg = 'Expense submitted';
        _future = ApiClient.instance.expenses();
      });
    } catch (e) {
      SoundHelper.playFailure();
      setState(() => _msg = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  void _showPaymentQR(BuildContext context, String amount, String title) {
    // UPI payment string format: upi://pay?pa=VPA&pn=NAME&am=AMOUNT&cu=INR&tn=NOTE
    final upiString =
        'upi://pay?pa=connectingpoint@icici&pn=Connecting Point&am=$amount&cu=INR&tn=$title';

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text(
          'Scan to Pay',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            QrImageView(
              data: upiString,
              version: QrVersions.auto,
              size: 250.0,
              backgroundColor: Colors.white,
            ),
            const SizedBox(height: 16),
            Text(
              '₹$amount',
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.green,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'UPI ID: connectingpoint@icici',
              style: TextStyle(fontSize: 14, color: Colors.black54),
            ),
            const SizedBox(height: 8),
            Text(
              title,
              style: const TextStyle(
                fontSize: 14,
                color: Colors.black87,
                fontWeight: FontWeight.w500,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Expenses')),
      drawer: const AppDrawer(current: AppMenu.expenses),
      body: AppBackground(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextField(
              controller: _title,
              decoration: const InputDecoration(labelText: 'Title'),
            ),
            TextField(
              controller: _amount,
              decoration: const InputDecoration(labelText: 'Amount'),
            ),
            TextField(
              controller: _date,
              decoration: const InputDecoration(labelText: 'Date (YYYY-MM-DD)'),
            ),
            TextField(
              controller: _desc,
              decoration: const InputDecoration(labelText: 'Description'),
            ),
            const SizedBox(height: 8),
            ElevatedButton(
              onPressed: _pickPhoto,
              child: const Text('Add Bill Photo'),
            ),
            if (_photo != null) const Text('Photo selected'),
            const SizedBox(height: 8),
            ElevatedButton(
              onPressed: _loading ? null : _submit,
              child: const Text('Submit Expense'),
            ),
            if (_msg != null)
              Padding(padding: const EdgeInsets.all(8), child: Text(_msg!)),
            const Divider(height: 24, thickness: 2, color: Colors.white70),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.9),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Text(
                'Expense History',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 18,
                  color: Colors.black87,
                ),
              ),
            ),
            const SizedBox(height: 8),
            FutureBuilder(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.red.shade100,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      snapshot.error.toString(),
                      style: const TextStyle(
                        color: Colors.black87,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  );
                }
                final list = snapshot.data as List<Map<String, dynamic>>;
                if (list.isEmpty) {
                  return Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.9),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text(
                      'No expenses found',
                      style: TextStyle(
                        color: Colors.black87,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  );
                }
                return Column(
                  children: list.map((e) {
                    final status = e['status'] ?? '';
                    final isApproved =
                        status.toString().toLowerCase() == 'approved';
                    final isRejected =
                        status.toString().toLowerCase() == 'rejected';
                    final amount = e['amount'] ?? '0';
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      color: isApproved
                          ? Colors.green.shade50
                          : isRejected
                          ? Colors.red.shade50
                          : Colors.white,
                      child: Column(
                        children: [
                          ListTile(
                            title: Text(
                              '${e['title'] ?? ''} - ₹$amount',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                                color: Colors.black87,
                              ),
                            ),
                            subtitle: Text(
                              '${e['expense_date'] ?? ''} | $status',
                              style: TextStyle(
                                fontSize: 14,
                                color: isApproved
                                    ? Colors.green.shade700
                                    : isRejected
                                    ? Colors.red.shade700
                                    : Colors.black87,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                          if (isApproved)
                            Padding(
                              padding: const EdgeInsets.only(
                                left: 16,
                                right: 16,
                                bottom: 12,
                              ),
                              child: SizedBox(
                                width: double.infinity,
                                child: ElevatedButton.icon(
                                  onPressed: () => _showPaymentQR(
                                    context,
                                    amount,
                                    e['title'] ?? 'Expense',
                                  ),
                                  icon: const Icon(Icons.qr_code),
                                  label: const Text('Pay Now'),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.green,
                                    foregroundColor: Colors.white,
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    );
                  }).toList(),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class AdvancePage extends StatefulWidget {
  const AdvancePage({super.key});

  @override
  State<AdvancePage> createState() => _AdvancePageState();
}

class _AdvancePageState extends State<AdvancePage> {
  final _amount = TextEditingController();
  final _reason = TextEditingController();
  String? _msg;
  bool _loading = false;
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiClient.instance.advances();
  }

  Future<void> _submit() async {
    setState(() {
      _loading = true;
      _msg = null;
    });
    try {
      await ApiClient.instance.requestAdvance(
        amount: _amount.text.trim(),
        reason: _reason.text.trim(),
      );
      SoundHelper.playSuccess();
      setState(() {
        _msg = 'Advance request submitted';
        _future = ApiClient.instance.advances();
      });
    } catch (e) {
      SoundHelper.playFailure();
      setState(() => _msg = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Request Advance')),
      drawer: const AppDrawer(current: AppMenu.advance),
      body: AppBackground(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextField(
              controller: _amount,
              decoration: const InputDecoration(labelText: 'Amount'),
            ),
            TextField(
              controller: _reason,
              decoration: const InputDecoration(labelText: 'Reason'),
            ),
            const SizedBox(height: 8),
            ElevatedButton(
              onPressed: _loading ? null : _submit,
              child: const Text('Submit Request'),
            ),
            if (_msg != null)
              Padding(padding: const EdgeInsets.all(8), child: Text(_msg!)),
            const Divider(height: 24),
            const Text(
              'Past Requests',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            FutureBuilder(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Text(snapshot.error.toString());
                }
                final list = snapshot.data as List<Map<String, dynamic>>;
                if (list.isEmpty) {
                  return const Text('No requests found');
                }
                return Column(
                  children: list.map((r) {
                    return ListTile(
                      title: Text('₹${r['amount'] ?? ''}'),
                      subtitle: Text(
                        '${r['request_date'] ?? ''} | ${r['status'] ?? ''}',
                      ),
                    );
                  }).toList(),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

enum AppMenu {
  attendance,
  records,
  expenses,
  advance,
  myWork,
  assignWork,
  workRecords,
  profile,
}

class AppDrawer extends StatelessWidget {
  final AppMenu current;
  const AppDrawer({super.key, required this.current});

  void _openPrivacy(BuildContext context) {
    Navigator.of(
      context,
    ).push(MaterialPageRoute(builder: (_) => const PrivacyPolicyPage()));
  }

  Future<void> _changeProfilePhoto(BuildContext context) async {
    final ImagePicker picker = ImagePicker();
    final XFile? photo = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 75,
    );

    if (photo == null) return;

    try {
      // Crop the image
      final croppedFile = await ImageCropper().cropImage(
        sourcePath: photo.path,
        aspectRatio: const CropAspectRatio(ratioX: 1, ratioY: 1),
        uiSettings: [
          AndroidUiSettings(
            toolbarTitle: 'Crop Profile Photo',
            toolbarColor: Colors.blueGrey,
            toolbarWidgetColor: Colors.white,
            lockAspectRatio: true,
          ),
          IOSUiSettings(
            title: 'Crop Profile Photo',
            aspectRatioLockEnabled: true,
          ),
        ],
      );

      if (croppedFile == null) return;

      final bytes = await croppedFile.readAsBytes();

      // Upload to server
      await ApiClient.instance.uploadProfilePhoto(bytes);

      // Reload session data
      final userData = await ApiClient.instance.me();
      session.profilePhoto = userData['profile_photo'];

      if (context.mounted) {
        SoundHelper.playSuccess();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Profile photo updated successfully!')),
        );
        // Refresh the drawer
        Navigator.of(context).pop();
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const AttendancePage()),
        );
      }
    } catch (e) {
      if (context.mounted) {
        SoundHelper.playFailure();
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error updating photo: $e')));
      }
    }
  }

  void _go(BuildContext context, AppMenu target, Widget page) {
    if (current == target) {
      Navigator.of(context).pop();
      return;
    }
    Navigator.of(
      context,
    ).pushReplacement(MaterialPageRoute(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final isManager = session.manager;
    final isShopManager = session.shopManager;
    return Drawer(
      child: Column(
        children: [
          Expanded(
            child: ListView(
              children: [
                DrawerHeader(
                  decoration: const BoxDecoration(color: Colors.blueGrey),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          GestureDetector(
                            onTap: () => _changeProfilePhoto(context),
                            child: Stack(
                              children: [
                                CircleAvatar(
                                  radius: 35,
                                  backgroundColor: Colors.white,
                                  backgroundImage: session.profilePhoto != null
                                      ? NetworkImage(session.profilePhoto!)
                                      : null,
                                  child: session.profilePhoto == null
                                      ? Text(
                                          session.name
                                                  ?.substring(0, 1)
                                                  .toUpperCase() ??
                                              'U',
                                          style: const TextStyle(
                                            fontSize: 28,
                                            fontWeight: FontWeight.bold,
                                            color: Colors.blueGrey,
                                          ),
                                        )
                                      : null,
                                ),
                                Positioned(
                                  bottom: 0,
                                  right: 0,
                                  child: Container(
                                    padding: const EdgeInsets.all(4),
                                    decoration: const BoxDecoration(
                                      color: Colors.white,
                                      shape: BoxShape.circle,
                                    ),
                                    child: const Icon(
                                      Icons.camera_alt,
                                      size: 16,
                                      color: Colors.blueGrey,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Text(
                                  'Employee Menu',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  session.name ?? '',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 15,
                                    fontWeight: FontWeight.w600,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                Text(
                                  session.mobile ?? '',
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    fontSize: 13,
                                  ),
                                ),
                                Text(
                                  session.companyName ?? 'Company',
                                  style: const TextStyle(
                                    color: Colors.white70,
                                    fontSize: 12,
                                  ),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                ListTile(
                  title: const Text('Attendance'),
                  selected: current == AppMenu.attendance,
                  onTap: () =>
                      _go(context, AppMenu.attendance, const AttendancePage()),
                ),
                ListTile(
                  title: const Text('View Records'),
                  selected: current == AppMenu.records,
                  onTap: () => _go(
                    context,
                    AppMenu.records,
                    const AttendanceRecordsPage(),
                  ),
                ),
                ListTile(
                  title: const Text('My Expenses'),
                  selected: current == AppMenu.expenses,
                  onTap: () =>
                      _go(context, AppMenu.expenses, const ExpensesPage()),
                ),
                ListTile(
                  title: const Text('Request Advance'),
                  selected: current == AppMenu.advance,
                  onTap: () =>
                      _go(context, AppMenu.advance, const AdvancePage()),
                ),
                ListTile(
                  title: const Text('My Work'),
                  selected: current == AppMenu.myWork,
                  onTap: () => _go(context, AppMenu.myWork, const MyWorkPage()),
                ),
                if (isManager || isShopManager)
                  ListTile(
                    title: const Text('Assign Work'),
                    selected: current == AppMenu.assignWork,
                    onTap: () => _go(
                      context,
                      AppMenu.assignWork,
                      const WorkAssignPage(),
                    ),
                  ),
                if (isManager)
                  ListTile(
                    title: const Text('Work Records'),
                    selected: current == AppMenu.workRecords,
                    onTap: () => _go(
                      context,
                      AppMenu.workRecords,
                      const WorkRecordsPage(),
                    ),
                  ),
                const Divider(),
                ListTile(
                  leading: const Icon(Icons.person),
                  title: const Text('My Profile'),
                  selected: current == AppMenu.profile,
                  onTap: () =>
                      _go(context, AppMenu.profile, const ProfilePage()),
                ),
                ListTile(
                  leading: const Icon(Icons.privacy_tip),
                  title: const Text('Privacy Policy'),
                  onTap: () => _openPrivacy(context),
                ),
              ],
            ),
          ),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            color: Colors.grey.shade200,
            child: const Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Powered by',
                  style: TextStyle(fontSize: 11, color: Colors.grey),
                ),
                SizedBox(height: 4),
                Text(
                  'Connecting Point',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Colors.blueGrey,
                  ),
                ),
                SizedBox(height: 2),
                Text(
                  '@360vision.in',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.blue,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class SetupPage extends StatefulWidget {
  const SetupPage({super.key});

  @override
  State<SetupPage> createState() => _SetupPageState();
}

class _SetupPageState extends State<SetupPage> {
  final _company = TextEditingController();
  final _mobile = TextEditingController();
  final _password = TextEditingController();
  String? _msg;

  Future<void> _load() async {
    final creds = await AppPrefs.readCredentials();
    if (creds == null) return;
    _company.text = creds['company'] ?? '';
    _mobile.text = creds['mobile'] ?? '';
    _password.text = creds['password'] ?? '';
    setState(() {});
  }

  Future<void> _saveAndLogin() async {
    await AppPrefs.saveCredentials(
      company: _company.text.trim(),
      mobile: _mobile.text.trim(),
      password: _password.text,
    );
    try {
      await ApiClient.instance.login(
        mobile: _mobile.text.trim(),
        password: _password.text,
        companyCode: _company.text.trim(),
      );
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const AttendancePage()),
        (route) => false,
      );
    } catch (e) {
      setState(() => _msg = e.toString());
    }
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Setup Company')),
      body: AppBackground(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _company,
                decoration: const InputDecoration(labelText: 'Company Code'),
              ),
              TextField(
                controller: _mobile,
                decoration: const InputDecoration(labelText: 'Mobile'),
              ),
              TextField(
                controller: _password,
                obscureText: true,
                decoration: const InputDecoration(labelText: 'Password'),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: _saveAndLogin,
                child: const Text('Save & Login'),
              ),
              TextButton(
                onPressed: () async {
                  final uri = Uri.parse(kPrivacyUrl);
                  if (!await launchUrl(
                    uri,
                    mode: LaunchMode.externalApplication,
                  )) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text('Unable to open privacy policy'),
                        ),
                      );
                    }
                  }
                },
                child: const Text('Privacy Policy'),
              ),
              if (_msg != null)
                Padding(padding: const EdgeInsets.all(8), child: Text(_msg!)),
            ],
          ),
        ),
      ),
    );
  }
}

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiClient.instance.me();
  }

  Future<void> _changePhoto() async {
    final ImagePicker picker = ImagePicker();
    final XFile? photo = await picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 75,
    );

    if (photo == null) return;

    try {
      // Crop the image
      final croppedFile = await ImageCropper().cropImage(
        sourcePath: photo.path,
        aspectRatio: const CropAspectRatio(ratioX: 1, ratioY: 1),
        uiSettings: [
          AndroidUiSettings(
            toolbarTitle: 'Crop Profile Photo',
            toolbarColor: Colors.blueGrey,
            toolbarWidgetColor: Colors.white,
            lockAspectRatio: true,
          ),
          IOSUiSettings(
            title: 'Crop Profile Photo',
            aspectRatioLockEnabled: true,
          ),
        ],
      );

      if (croppedFile == null) return;

      final bytes = await croppedFile.readAsBytes();

      // Upload to server
      await ApiClient.instance.uploadProfilePhoto(bytes);

      // Reload data
      setState(() {
        _future = ApiClient.instance.me();
      });

      if (mounted) {
        SoundHelper.playSuccess();
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Profile photo updated!')));
      }
    } catch (e) {
      if (mounted) {
        SoundHelper.playFailure();
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _launchEmployeeProfile() async {
    final url = Uri.parse('https://att.connectingpoint.in/employee');
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.inAppBrowserView);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'My Profile',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.blueGrey,
        foregroundColor: Colors.white,
      ),
      drawer: const AppDrawer(current: AppMenu.profile),
      body: AppBackground(
        child: FutureBuilder(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return Center(
                child: Text(
                  'Error: ${snapshot.error}',
                  style: const TextStyle(color: Colors.white),
                ),
              );
            }
            final data = snapshot.data as Map<String, dynamic>;
            session.profilePhoto = data['profile_photo'];
            session.companyName = data['company_name'];

            return SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  GestureDetector(
                    onTap: _changePhoto,
                    child: Stack(
                      children: [
                        CircleAvatar(
                          radius: 60,
                          backgroundColor: Colors.white,
                          backgroundImage: session.profilePhoto != null
                              ? NetworkImage(session.profilePhoto!)
                              : null,
                          child: session.profilePhoto == null
                              ? Text(
                                  session.name?.substring(0, 1).toUpperCase() ??
                                      'U',
                                  style: const TextStyle(
                                    fontSize: 48,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.blueGrey,
                                  ),
                                )
                              : null,
                        ),
                        Positioned(
                          bottom: 0,
                          right: 0,
                          child: Container(
                            padding: const EdgeInsets.all(8),
                            decoration: const BoxDecoration(
                              color: Colors.blueGrey,
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(
                              Icons.camera_alt,
                              size: 20,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),
                  _buildInfoCard('Name', data['name'] ?? 'N/A'),
                  _buildInfoCard('Mobile', data['mobile'] ?? 'N/A'),
                  _buildInfoCard('Company', data['company_name'] ?? 'N/A'),
                  _buildInfoCard(
                    'Employee ID',
                    data['id']?.toString() ?? 'N/A',
                  ),
                  _buildInfoCard(
                    'Manager',
                    data['manager_role'] == true ? 'Yes' : 'No',
                  ),
                  _buildInfoCard(
                    'Shop Manager',
                    data['shop_manager_role'] == true ? 'Yes' : 'No',
                  ),
                  _buildInfoCard(
                    'Vehicle Log',
                    data['vehicle_log_enabled'] == true
                        ? 'Enabled'
                        : 'Disabled',
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton.icon(
                    onPressed: () async {
                      final url = Uri.parse(
                        'https://att.connectingpoint.in/profile',
                      );
                      if (await canLaunchUrl(url)) {
                        await launchUrl(url, mode: LaunchMode.inAppBrowserView);
                      }
                    },
                    icon: const Icon(Icons.open_in_browser),
                    label: const Text('Open Full Profile'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blueGrey,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 24,
                        vertical: 12,
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildInfoCard(String label, String value) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.black54,
              ),
            ),
            Expanded(
              child: Text(
                value,
                textAlign: TextAlign.right,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Colors.black87,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class WorkRecordsPage extends StatefulWidget {
  const WorkRecordsPage({super.key});

  @override
  State<WorkRecordsPage> createState() => _WorkRecordsPageState();
}

class _WorkRecordsPageState extends State<WorkRecordsPage> {
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiClient.instance.workRecords();
  }

  void _showWorkDetail(Map<String, dynamic> work) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Colors.white,
        title: Text(
          work['customer_name'] ?? 'Work Details',
          style: const TextStyle(
            fontWeight: FontWeight.bold,
            color: Colors.black87,
          ),
        ),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildDetailRow('Employee', work['emp_name'] ?? 'N/A'),
              _buildDetailRow('Mobile', work['customer_mobile'] ?? 'N/A'),
              _buildDetailRow('Address', work['customer_address'] ?? 'N/A'),
              _buildDetailRow('Location', work['customer_location'] ?? 'N/A'),
              _buildDetailRow('Service Type', work['service_type'] ?? 'N/A'),
              _buildDetailRow('Status', work['status'] ?? 'N/A'),
              _buildDetailRow('Amount', '₹${work['amount'] ?? '0'}'),
              _buildDetailRow(
                'Payment',
                work['payment_method']?.toString().toUpperCase() ?? 'N/A',
              ),
              _buildDetailRow('Duration', work['duration'] ?? 'N/A'),
              _buildDetailRow('Assigned', work['assigned_at'] ?? 'N/A'),
              if (work['started_at'] != null)
                _buildDetailRow('Started', work['started_at']),
              if (work['completed_at'] != null)
                _buildDetailRow('Completed', work['completed_at']),
              if (work['notes'] != null && work['notes'].toString().isNotEmpty)
                _buildDetailRow('Notes', work['notes']),
              if (work['checkout_photo'] != null) ...[
                const SizedBox(height: 12),
                const Text(
                  'Checkout Photo:',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Colors.black87,
                  ),
                ),
                const SizedBox(height: 8),
                GestureDetector(
                  onTap: () => _downloadPhoto(work['checkout_photo']),
                  child: Container(
                    height: 150,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey.shade300, width: 2),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(6),
                      child: Stack(
                        children: [
                          Image.network(
                            work['checkout_photo'],
                            width: double.infinity,
                            fit: BoxFit.cover,
                            errorBuilder: (context, error, stack) =>
                                const Center(
                                  child: Icon(Icons.error, size: 50),
                                ),
                          ),
                          Positioned(
                            bottom: 8,
                            right: 8,
                            child: Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: Colors.black54,
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: const Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.download,
                                    color: Colors.white,
                                    size: 16,
                                  ),
                                  SizedBox(width: 4),
                                  Text(
                                    'Tap to Download',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 12,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<void> _downloadPhoto(String photoUrl) async {
    try {
      final uri = Uri.parse(photoUrl);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        if (mounted) {
          SoundHelper.playSuccess();
          ScaffoldMessenger.of(
            context,
          ).showSnackBar(const SnackBar(content: Text('Opening photo...')));
        }
      } else {
        throw Exception('Could not open photo URL');
      }
    } catch (e) {
      if (mounted) {
        SoundHelper.playFailure();
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error opening photo: $e')));
      }
    }
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 100,
            child: Text(
              '$label:',
              style: const TextStyle(
                fontWeight: FontWeight.bold,
                color: Colors.black54,
              ),
            ),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(color: Colors.black87)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Work Records',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.blueGrey,
        foregroundColor: Colors.white,
      ),
      drawer: const AppDrawer(current: AppMenu.workRecords),
      body: AppBackground(
        child: FutureBuilder(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(
                child: CircularProgressIndicator(color: Colors.white),
              );
            }
            if (snapshot.hasError) {
              return Center(
                child: Text(
                  snapshot.error.toString(),
                  style: const TextStyle(color: Colors.white),
                ),
              );
            }
            final list = snapshot.data as List<Map<String, dynamic>>;

            if (list.isEmpty) {
              return const Center(
                child: Text(
                  'No work records found',
                  style: TextStyle(color: Colors.white, fontSize: 16),
                ),
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(8),
              itemCount: list.length,
              itemBuilder: (context, i) {
                final r = list[i];
                final status = r['status']?.toString().toLowerCase() ?? '';
                Color cardColor;
                Color borderColor;

                if (status.contains('completed')) {
                  cardColor = Colors.green.shade50;
                  borderColor = Colors.green;
                } else if (status.contains('hold')) {
                  cardColor = Colors.red.shade50;
                  borderColor = Colors.red;
                } else if (status.contains('pending')) {
                  cardColor = Colors.orange.shade50;
                  borderColor = Colors.orange;
                } else if (status.contains('progress') ||
                    status.contains('started')) {
                  cardColor = Colors.blue.shade50;
                  borderColor = Colors.blue;
                } else {
                  cardColor = Colors.grey.shade50;
                  borderColor = Colors.grey;
                }

                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  color: cardColor,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(color: borderColor, width: 2),
                  ),
                  child: InkWell(
                    onTap: () => _showWorkDetail(r),
                    borderRadius: BorderRadius.circular(12),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          // Photo thumbnail
                          if (r['checkout_photo'] != null)
                            Container(
                              margin: const EdgeInsets.only(right: 12),
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: borderColor,
                                  width: 2,
                                ),
                              ),
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(6),
                                child: Image.network(
                                  r['checkout_photo'],
                                  width: 60,
                                  height: 60,
                                  fit: BoxFit.cover,
                                  errorBuilder: (context, error, stack) =>
                                      Container(
                                        width: 60,
                                        height: 60,
                                        color: Colors.grey.shade200,
                                        child: const Icon(
                                          Icons.image,
                                          color: Colors.grey,
                                        ),
                                      ),
                                ),
                              ),
                            ),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        r['customer_name'] ?? 'Unknown',
                                        style: const TextStyle(
                                          fontSize: 18,
                                          fontWeight: FontWeight.bold,
                                          color: Colors.black87,
                                        ),
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 4,
                                      ),
                                      decoration: BoxDecoration(
                                        color: borderColor,
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Text(
                                        r['status'] ?? '',
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 12,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Employee: ${r['emp_name'] ?? 'N/A'}',
                                  style: const TextStyle(
                                    fontSize: 14,
                                    color: Colors.black87,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  'Service: ${r['service_type'] ?? 'N/A'}',
                                  style: const TextStyle(
                                    fontSize: 14,
                                    color: Colors.black54,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  'Amount: ₹${r['amount'] ?? '0'} (${r['payment_method']?.toString().toUpperCase() ?? 'CASH'})',
                                  style: const TextStyle(
                                    fontSize: 14,
                                    color: Colors.green,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                if (r['duration'] != null)
                                  Padding(
                                    padding: const EdgeInsets.only(top: 2),
                                    child: Text(
                                      'Duration: ${r['duration']}',
                                      style: const TextStyle(
                                        fontSize: 13,
                                        color: Colors.black54,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                  ),
                                const SizedBox(height: 4),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.end,
                                  children: [
                                    Text(
                                      'Tap for details',
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: borderColor,
                                        fontStyle: FontStyle.italic,
                                      ),
                                    ),
                                    Icon(
                                      Icons.arrow_forward_ios,
                                      size: 12,
                                      color: borderColor,
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class AppBackground extends StatelessWidget {
  final Widget child;
  const AppBackground({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Positioned.fill(
          child: Image.asset(kBackgroundImage, fit: BoxFit.cover),
        ),
        Positioned.fill(child: Container(color: Colors.black.withOpacity(0.2))),
        child,
      ],
    );
  }
}

class PrivacyPolicyPage extends StatelessWidget {
  const PrivacyPolicyPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Privacy Policy',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
        backgroundColor: Colors.blueGrey,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Privacy Policy',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: Colors.blueGrey,
              ),
            ),
            const SizedBox(height: 10),
            const Text(
              'Last updated: February 8, 2026',
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey,
                fontStyle: FontStyle.italic,
              ),
            ),
            const SizedBox(height: 20),
            _buildSection(
              'Introduction',
              'This Privacy Policy describes how we collect, use, and protect your personal information when you use our Attendance Mobile application.',
            ),
            _buildSection(
              'Information We Collect',
              'We collect the following information:\\n\\n• Location data (GPS coordinates) for attendance tracking\\n• Photos for attendance verification\\n• Employee information (name, mobile number, company code)\\n• Work assignment and expense details\\n• Attendance records and timestamps',
            ),
            _buildSection(
              'How We Use Your Information',
              'Your information is used for:\\n\\n• Recording and tracking employee attendance\\n• Verifying your identity through photos\\n• Managing work assignments and tasks\\n• Processing expense claims\\n• Generating attendance reports\\n• Communicating work-related information',
            ),
            _buildSection(
              'Data Security',
              'We implement appropriate security measures to protect your personal information from unauthorized access, alteration, disclosure, or destruction. All data is transmitted securely over HTTPS.',
            ),
            _buildSection(
              'Location Data',
              'Location permissions are required to record your attendance location. GPS data is collected only when you punch in or out, and is used solely for attendance verification purposes.',
            ),
            _buildSection(
              'Photo Data',
              'Camera permissions are required to capture attendance photos. Photos are securely transmitted to our servers and stored for attendance verification and record-keeping purposes.',
            ),
            _buildSection(
              'Data Retention',
              'We retain your attendance records and related data as long as you remain an active employee or as required by applicable labor laws and regulations.',
            ),
            _buildSection(
              'Your Rights',
              'You have the right to:\\n\\n• Access your personal data\\n• Request corrections to inaccurate data\\n• Request deletion of your data (subject to legal requirements)\\n• Withdraw consent for data processing',
            ),
            _buildSection(
              'Contact Us',
              'If you have any questions about this Privacy Policy, please contact us at:\\n\\nConnecting Point\\nEmail: 360vision.in\\nWebsite: att.connectingpoint.in',
            ),
            const SizedBox(height: 30),
            Center(
              child: ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blueGrey,
                  foregroundColor: Colors.white,
                ),
                child: const Text('Close'),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildSection(String title, String content) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Colors.black87,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            content,
            style: const TextStyle(
              fontSize: 15,
              height: 1.5,
              color: Colors.black87,
            ),
          ),
        ],
      ),
    );
  }
}
