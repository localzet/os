import unittest
from localzet.proxy_policy import render_policy


class ProxyPolicyTests(unittest.TestCase):
    def test_only_exact_endpoint(self):
        for address, family in (("192.0.2.2", "ip"), ("2001:db8::2", "ip6")):
            policy = render_policy(address, 7890)
            self.assertIn("policy drop;", policy)
            self.assertIn(f"{family} daddr {address} tcp dport 7890 counter accept", policy)
            self.assertEqual(policy.count("accept"), 1)
            self.assertNotIn("established", policy)

    def test_reject_invalid_endpoints(self):
        for address in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "::",
                        "224.0.0.1", "ff02::1", "169.254.1.1", "fe80::1",
                        "::ffff:192.0.2.2", "2001:db8::2%eth0", "192.0.2.2; accept"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                render_policy(address, 7890)
        for port in (0, -1, 65536, True, "7890"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                render_policy("192.0.2.2", port)
