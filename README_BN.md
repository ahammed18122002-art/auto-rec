# Echo Recon — Linux Edition · echo 2026.10

এটি একটি Linux-only desktop recon dashboard; Windows ও WSL launcher এই সংস্করণে নেই। GUI-টি সহজ Chrome-ধাঁচের header, উপরে toolchain readiness indicator, target/control area এবং বড় Live Terminal দিয়ে সাজানো। GUI minimize করা যায় এবং scan চলার সময় step-by-step stdout/stderr output, installer log ও report path দেখা যায়।

## দ্রুত চালানো

```bash
chmod +x run.sh install_linux.sh
./run.sh
```

প্রথম চালুতে GUI নিজে ১৪টি requirement tool-এর status পরীক্ষা করে। উপরে সব tools থাকলে সবুজ status দেখাবে; কোনোটি অনুপস্থিত বা যাচাই করা না গেলে লাল status এবং missing নামগুলো দেখাবে।

### Download all repositories

1. উপরের `sudo password (not saved)` বক্সে আপনার Linux sudo password দিন।
2. `Download all repositories` চাপুন।
3. পাসওয়ার্ড কেবল `sudo`-এর stdin-এ পাঠানো হয়; command-line argument, log বা configuration file-এ রাখা হয় না। ভুল হলে installer output থেকে error শনাক্ত করে GUI-তে password error দেখায়।
4. Installer apt packages, Go toolchain/tool binaries, pipx/official release/source fallback স্থাপন করার চেষ্টা করে। শেষে tool status আবার পরীক্ষা করুন। কোনো repository/package unavailable বা build fail করলে সেটি output panel-এ warning দেখাবে—এক ক্লিকে সব ১৪টি স্থাপিত হওয়ার নিশ্চয়তা দেওয়া হয় না।

`tool_repositories.json` এবং `TOOL_REPOSITORIES.md`-এ ১৪টি tool-এর official upstream links ও install method আছে। ProjectDiscovery tools তাদের official Go module path থেকে build করা হয়; Nmap/অন্যান্য apt packages configured distro repository থেকে আসে। Go SDK প্রয়োজন হলে installer Go-এর official release metadata থেকে SHA-256 যাচাই করে user-local জায়গায় রাখার চেষ্টা করে। Feroxbuster official release fallback-ও digest পাওয়া গেলে SHA-256 যাচাই করে।

## GUI থেকে scan

- টার্গেট domain/URL লিখুন এবং permission checkbox tick করুন।
- প্রয়োজনীয় tool নির্বাচন করুন; উচ্চ request-সম্ভাবনাযুক্ত content discovery/parameter test tools ডিফল্টভাবে unchecked থাকে।
- Per-tool watchdog 900, 1800, 3600 বা 7200 seconds থেকে বেছে নিন। Stop চাপলে চলমান process group বন্ধ করার চেষ্টা হয় এবং আগের output partial report-এ রাখা হয়।
- `outputs/<run-id>/`-এ raw tool logs এবং HTML/JSON/Markdown reports তৈরি হয়।

## Tool status ও PATH

Application user-local binaries `~/.local/bin` এবং `~/go/bin`-ও পরীক্ষা করে; GUI থেকে launch করলেও একই path child tools-এ দেওয়া হয়। `httpx`-এর ক্ষেত্রে ProjectDiscovery CLI আলাদা করে version-banner দিয়ে যাচাই করা হয়।

## পরীক্ষা

```bash
./run.sh --test
./run.sh --check-tools
./run.sh --version
```

Tests হলো offline unit/regression tests; এগুলো real target scan, distribution-specific package availability বা GUI rendering পরীক্ষা করে না। নিজের বা স্পষ্ট অনুমতিপ্রাপ্ত asset-এ সক্রিয় scan চালান। Rate cap থাকলেও কোনো target-এ load/alert হতে পারে।
