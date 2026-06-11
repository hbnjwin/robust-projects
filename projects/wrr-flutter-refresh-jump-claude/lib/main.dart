import 'package:flutter/material.dart';
import 'package:pull_to_refresh/pull_to_refresh.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(home: const RefreshListPage());
  }
}

class RefreshListPage extends StatefulWidget {
  const RefreshListPage({super.key});
  @override
  State<RefreshListPage> createState() => _RefreshListPageState();
}

class _RefreshListPageState extends State<RefreshListPage> {
  final RefreshController _refreshController = RefreshController();
  List<String> items = List.generate(20, (i) => 'Item ${i + 1}');

  void _onRefresh() async {
    await Future.delayed(const Duration(seconds: 1));
    setState(() {
      items = List.generate(20, (i) => 'Refreshed Item ${i + 1}');
    });
    _refreshController.refreshCompleted();
    // BUG: scroll position jumps after refresh on iOS
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('List')),
      body: SmartRefresher(
        controller: _refreshController,
        onRefresh: _onRefresh,
        child: ListView.builder(
          itemCount: items.length,
          itemBuilder: (_, i) => ListTile(title: Text(items[i])),
        ),
      ),
    );
  }
}
