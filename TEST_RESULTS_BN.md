# Echo Recon Linux Edition — Test Results

## স্বয়ংক্রিয় পরীক্ষা

| পরীক্ষা | ফলাফল | বিস্তারিত |
|---|---|---|
| Python syntax compile | PASS | `python3 -m compileall -q .` |
| Offline regression tests | PASS | ২২টি test: scope/URL validation, tool registry, repository-link registry, path handling, report escaping, command argument safety, process success/failure/timeout/cancellation এবং sudo-password flow mock |
| Shell syntax | PASS | `bash -n install_linux.sh` এবং `bash -n run.sh` |
| GUI smoke test | PASS | Xvfb virtual display-তে GUI তৈরি, version title, startup tool check এবং terminal widget যাচাই |
| CLI version | PASS | `./run.sh --version` → `Echo Recon echo 2026.10` |
| Tool-check JSON | PASS | `./run.sh --check-tools`; ১৪টি tool-এর JSON status parse হয়েছে |
| ZIP integrity | PASS | `unzip -t echo-recon-linux-package.zip` সফল |

## যা বাস্তবভাবে চালানো হয়নি

- এই পরীক্ষার পরিবেশে ১৪টি external scanner executable-এর **০টি** পাওয়া গেছে। তাই প্রকৃত Nmap/Nuclei/Subfinder ইত্যাদি দিয়ে live target scan করা হয়নি।
- `Download all repositories`-এর বাস্তব apt/Go/GitHub download এবং প্রকৃত sudo password authentication চালানো হয়নি; password error handling mocked regression test দিয়ে যাচাই করা হয়েছে।
- GUI-এর visual smoke test Xvfb-তে হয়েছে, তবে Kali/Debian/Ubuntu-র প্রকৃত desktop session-এ user acceptance test বাকি।
- এই প্যাকেজটি স্বতন্ত্র Linux edition; নির্দিষ্ট upstream GitHub repository-র সব ফাইলের সঙ্গে one-to-one audited patch হিসেবে দাবি করা হচ্ছে না।

এই পরীক্ষাগুলো স্থানীয় regression কমাতে সাহায্য করে, কিন্তু ১৪টি টুলের সব CLI flag বা distro package compatibility নিশ্চিত করে না। আপনার Linux মেশিনে `Download all repositories` চালানোর পর readiness status পুনরায় দেখুন এবং প্রথম অনুমোদিত scan-এর raw logs পর্যালোচনা করুন।
