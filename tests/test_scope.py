import unittest
from echo_recon.scope import parse_target, is_in_scope, filter_in_scope_hosts, redact_url, bound_active_hosts


class TargetScopeTests(unittest.TestCase):
    def test_domain_defaults_to_https(self):
        target = parse_target("Example.COM")
        self.assertEqual(target.host, "example.com")
        self.assertEqual(target.origin, "https://example.com")

    def test_url_retains_path_query_for_parameterized_tests(self):
        target = parse_target("https://example.com/item?id=1")
        self.assertEqual(target.path, "/item")
        self.assertTrue(target.has_query_parameters)
        self.assertEqual(target.url, "https://example.com/item?id=1")

    def test_non_http_scheme_rejected(self):
        with self.assertRaises(ValueError):
            parse_target("ftp://example.com")

    def test_credentials_rejected(self):
        with self.assertRaises(ValueError):
            parse_target("https://user:pass@example.com")

    def test_scope_matches_exact_or_child_only(self):
        self.assertTrue(is_in_scope("example.com", "example.com"))
        self.assertTrue(is_in_scope("api.example.com", "example.com"))
        self.assertFalse(is_in_scope("example.com.attacker.test", "example.com"))
        self.assertFalse(is_in_scope("attacker.test", "example.com"))

    def test_filter_discards_out_of_scope_hosts(self):
        found = filter_in_scope_hosts(["api.example.com", "example.com", "evil.test", "*.dev.example.com"], "example.com")
        self.assertEqual(found, ["api.example.com", "dev.example.com", "example.com"])

    def test_active_host_list_is_capped_and_keeps_root_first(self):
        discovered = [f"host{i}.example.com" for i in range(1, 140)]
        bounded = bound_active_hosts("example.com", discovered, max_hosts=20)
        self.assertEqual(len(bounded), 20)
        self.assertEqual(bounded[0], "example.com")
        self.assertTrue(all(is_in_scope(host, "example.com") for host in bounded))

    def test_query_values_are_redacted(self):
        self.assertEqual(redact_url("https://example.com/path?a=secret&b=2"),
                         "https://example.com/path?a=REDACTED&b=REDACTED")


if __name__ == "__main__":
    unittest.main()
