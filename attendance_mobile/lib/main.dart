import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';

const String kBackgroundImage = 'assets/images/background.png';
const String kPrivacyUrl = 'https://att.connectingpoint.in/privacy';

void main() {
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

  Future<void> _getLocation() async {
    final perm = await Geolocator.requestPermission();
    if (perm == LocationPermission.denied ||
        perm == LocationPermission.deniedForever) {
      setState(() => _msg = 'Location permission denied');
      return;
    }
    final pos = await Geolocator.getCurrentPosition();
    setState(() => _pos = pos);
  }

  Future<void> _addPhoto() async {
    final file = await _picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 75,
    );
    if (file == null) return;
    final bytes = await file.readAsBytes();
    setState(() => _photos.add(bytes));
  }

  Future<void> _submit() async {
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
      setState(() => _msg = 'Attendance submitted');
    } catch (e) {
      setState(() => _msg = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Attendance')),
      drawer: const AppDrawer(current: AppMenu.attendance),
      body: AppBackground(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Row(
                children: [
                  const Text('Action:'),
                  const SizedBox(width: 12),
                  DropdownButton<String>(
                    value: _action,
                    items: const [
                      DropdownMenuItem(value: 'in', child: Text('Punch In')),
                      DropdownMenuItem(value: 'out', child: Text('Punch Out')),
                    ],
                    onChanged: (v) => setState(() => _action = v ?? 'in'),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              ElevatedButton(
                onPressed: _getLocation,
                child: const Text('Get GPS'),
              ),
              ElevatedButton(
                onPressed: _addPhoto,
                child: const Text('Add Photo'),
              ),
              TextField(
                controller: _subject,
                decoration: const InputDecoration(
                  labelText: 'Subject (optional)',
                ),
              ),
              Text('Photos: ${_photos.length}'),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: _loading ? null : _submit,
                child: const Text('Submit'),
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
  final ImagePicker _picker = ImagePicker();
  Uint8List? _photo;
  Position? _pos;
  String? _msg;

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
    );
    await _load();
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
                      TextField(
                        controller: _amount,
                        decoration: const InputDecoration(
                          labelText: 'Amount (₹)',
                        ),
                      ),
                      ElevatedButton(
                        onPressed: _pickPhoto,
                        child: const Text('Capture Photo'),
                      ),
                      ElevatedButton(
                        onPressed: _checkout,
                        child: const Text('Check Out'),
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
      setState(() => _msg = 'Select employee');
      return;
    }
    await ApiClient.instance.assignWork({
      'assigned_to': _assignedTo,
      'customer_name': _customer.text,
      'customer_mobile': _mobile.text,
      'customer_address': _address.text,
      'customer_location': _location.text,
      'service_type': _service,
      'notes': _notes.text,
    });
    setState(() => _msg = 'Work assigned');
  }

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Work Assign')),
      drawer: const AppDrawer(current: AppMenu.assignWork),
      body: AppBackground(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: ListView(
            children: [
              DropdownButton<int>(
                value: _assignedTo,
                hint: const Text('Select employee'),
                items: _employees
                    .map(
                      (e) => DropdownMenuItem<int>(
                        value: e['id'],
                        child: Text('${e['name']} (${e['mobile']})'),
                      ),
                    )
                    .toList(),
                onChanged: (v) => setState(() => _assignedTo = v),
              ),
              TextField(
                controller: _customer,
                decoration: const InputDecoration(labelText: 'Customer Name'),
              ),
              TextField(
                controller: _mobile,
                decoration: const InputDecoration(labelText: 'Customer Mobile'),
              ),
              TextField(
                controller: _address,
                decoration: const InputDecoration(labelText: 'Address'),
              ),
              TextField(
                controller: _location,
                decoration: const InputDecoration(labelText: 'Location'),
              ),
              DropdownButton<String>(
                value: _service,
                items: const [
                  DropdownMenuItem(
                    value: 'Installation',
                    child: Text('Installation'),
                  ),
                  DropdownMenuItem(value: 'Demo', child: Text('Demo')),
                  DropdownMenuItem(
                    value: 'Camera Services',
                    child: Text('Camera Services'),
                  ),
                  DropdownMenuItem(
                    value: 'Computer Services',
                    child: Text('Computer Services'),
                  ),
                  DropdownMenuItem(
                    value: 'Printer Services',
                    child: Text('Printer Services'),
                  ),
                  DropdownMenuItem(
                    value: 'Network Installation',
                    child: Text('Network Installation'),
                  ),
                  DropdownMenuItem(
                    value: 'Network Breakdown',
                    child: Text('Network Breakdown'),
                  ),
                  DropdownMenuItem(value: 'Other', child: Text('Other')),
                ],
                onChanged: (v) =>
                    setState(() => _service = v ?? 'Installation'),
              ),
              TextField(
                controller: _notes,
                decoration: const InputDecoration(labelText: 'Notes'),
              ),
              const SizedBox(height: 12),
              ElevatedButton(onPressed: _assign, child: const Text('Assign')),
              if (_msg != null) Text(_msg!),
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
            if (list.isEmpty) {
              return const Center(child: Text('No records found'));
            }
            return ListView.builder(
              itemCount: list.length,
              itemBuilder: (context, i) {
                final r = list[i];
                return ListTile(
                  title: Text('${r['action'] ?? ''}'.toUpperCase()),
                  subtitle: Text(r['timestamp'] ?? ''),
                  trailing: Text(r['location'] ?? ''),
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
      setState(() {
        _msg = 'Expense submitted';
        _future = ApiClient.instance.expenses();
      });
    } catch (e) {
      setState(() => _msg = e.toString());
    } finally {
      setState(() => _loading = false);
    }
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
            const Divider(height: 24),
            const Text(
              'Expense History',
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
                  return const Text('No expenses found');
                }
                return Column(
                  children: list.map((e) {
                    return ListTile(
                      title: Text('${e['title'] ?? ''} - ${e['amount'] ?? ''}'),
                      subtitle: Text(
                        '${e['expense_date'] ?? ''} | ${e['status'] ?? ''}',
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
      setState(() {
        _msg = 'Advance request submitted';
        _future = ApiClient.instance.advances();
      });
    } catch (e) {
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
}

class AppDrawer extends StatelessWidget {
  final AppMenu current;
  const AppDrawer({super.key, required this.current});

  Future<void> _openPrivacy(BuildContext context) async {
    final uri = Uri.parse(kPrivacyUrl);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Unable to open privacy policy')),
        );
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
      child: ListView(
        children: [
          DrawerHeader(
            decoration: const BoxDecoration(color: Colors.blueGrey),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Employee Menu',
                  style: TextStyle(color: Colors.white, fontSize: 18),
                ),
                const SizedBox(height: 8),
                Text(
                  session.name ?? '',
                  style: const TextStyle(color: Colors.white),
                ),
                Text(
                  session.mobile ?? '',
                  style: const TextStyle(color: Colors.white70),
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
            onTap: () =>
                _go(context, AppMenu.records, const AttendanceRecordsPage()),
          ),
          ListTile(
            title: const Text('My Expenses'),
            selected: current == AppMenu.expenses,
            onTap: () => _go(context, AppMenu.expenses, const ExpensesPage()),
          ),
          ListTile(
            title: const Text('Request Advance'),
            selected: current == AppMenu.advance,
            onTap: () => _go(context, AppMenu.advance, const AdvancePage()),
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
              onTap: () =>
                  _go(context, AppMenu.assignWork, const WorkAssignPage()),
            ),
          if (isManager)
            ListTile(
              title: const Text('Work Records'),
              selected: current == AppMenu.workRecords,
              onTap: () =>
                  _go(context, AppMenu.workRecords, const WorkRecordsPage()),
            ),
          const Divider(),
          ListTile(
            title: const Text('Privacy Policy'),
            onTap: () => _openPrivacy(context),
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Work Records')),
      drawer: const AppDrawer(current: AppMenu.workRecords),
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
                final r = list[i];
                return ListTile(
                  title: Text('${r['customer_name']} (${r['emp_name']})'),
                  subtitle: Text(
                    'Service: ${r['service_type']} | ${r['status']}',
                  ),
                  trailing: Text(r['duration'] ?? ''),
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
        Positioned.fill(
          child: Container(color: Colors.white.withOpacity(0.68)),
        ),
        child,
      ],
    );
  }
}
