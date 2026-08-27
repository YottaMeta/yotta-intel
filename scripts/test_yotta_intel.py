#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""yotta-intel（元情）单元测试。

运行（在技能目录内）：python scripts/test_yotta_intel.py
或（仓库根）：python yottaskills/yotta-intel/scripts/test_yotta_intel.py
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yotta_intel as yi

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yotta_intel.py")


def run_cli(*args, stdin=None):
    """以子进程方式运行 CLI（Windows 下也保证 UTF-8 输出）。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, SCRIPT] + list(args),
        input=stdin, capture_output=True, encoding="utf-8", errors="replace", env=env,
    )


def types_of(records):
    return [r["type"] for r in records]


def values_of(records, ioc_type):
    return [r["value"] for r in records if r["type"] == ioc_type]


class TestIPV4(unittest.TestCase):
    def test_ipv4_basic(self):
        recs = yi.extract_iocs("连接来自 203.0.113.5")
        self.assertIn("203.0.113.5", values_of(recs, "ipv4"))

    def test_ipv4_private_kept(self):
        recs = yi.extract_iocs("内网 10.0.0.1 有异常")
        self.assertIn("10.0.0.1", values_of(recs, "ipv4"))

    def test_ipv4_invalid_octet_rejected(self):
        recs = yi.extract_iocs("999.1.1.1 不是合法地址")
        self.assertNotIn("999.1.1.1", values_of(recs, "ipv4"))

    def test_ipv4_leading_zero_normalized(self):
        recs = yi.extract_iocs("地址 010.0.0.1")
        self.assertIn("10.0.0.1", values_of(recs, "ipv4"))
        self.assertNotIn("010.0.0.1", values_of(recs, "ipv4"))

    def test_ipv4_not_domain(self):
        recs = yi.extract_iocs("1.2.3.44")
        self.assertNotIn("1.2.3.44", values_of(recs, "domain"))

    def test_ipv4_count_dedup(self):
        recs = yi.extract_iocs("203.0.113.5\n203.0.113.5\n203.0.113.5")
        v = [r for r in recs if r["type"] == "ipv4"]
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]["count"], 3)


class TestIPV6(unittest.TestCase):
    def test_ipv6_compressed(self):
        recs = yi.extract_iocs("IPv6 2001:db8::1")
        self.assertIn("2001:db8::1", values_of(recs, "ipv6"))

    def test_ipv6_full(self):
        recs = yi.extract_iocs("2001:0db8:0000:0000:0000:0000:0000:0001")
        self.assertIn("2001:db8::1", values_of(recs, "ipv6"))

    def test_ipv6_mapped(self):
        recs = yi.extract_iocs("::ffff:192.168.1.1")
        self.assertIn("::ffff:c0a8:101", values_of(recs, "ipv6"))

    def test_ipv6_in_url(self):
        recs = yi.extract_iocs("http://[2001:db8::1]/x")
        urls = values_of(recs, "url")
        self.assertTrue(any(u == "http://[2001:db8::1]/x" for u in urls))

    def test_ipv6_invalid_rejected(self):
        recs = yi.extract_iocs("12345:67890")
        self.assertNotIn("12345:67890", values_of(recs, "ipv6"))


class TestDomain(unittest.TestCase):
    def test_domain_basic(self):
        recs = yi.extract_iocs("evil.example.com")
        self.assertIn("evil.example.com", values_of(recs, "domain"))

    def test_domain_uppercase_normalized(self):
        recs = yi.extract_iocs("EVIL.Example.COM")
        self.assertIn("evil.example.com", values_of(recs, "domain"))

    def test_domain_trailing_dot(self):
        recs = yi.extract_iocs("example.com.")
        self.assertIn("example.com", values_of(recs, "domain"))

    def test_domain_idn_punycode(self):
        recs = yi.extract_iocs("例子.测试")
        self.assertIn("xn--fsqu00a.xn--0zwm56d", values_of(recs, "domain"))

    def test_domain_filename_md_not_domain(self):
        recs = yi.extract_iocs("README.md 是文档")
        self.assertNotIn("readme.md", values_of(recs, "domain"))

    def test_domain_filename_py_not_domain(self):
        recs = yi.extract_iocs("test.py 是脚本")
        self.assertNotIn("test.py", values_of(recs, "domain"))

    def test_domain_filename_sh_not_domain(self):
        recs = yi.extract_iocs("install.sh")
        self.assertNotIn("install.sh", values_of(recs, "domain"))

    def test_domain_unknown_tld_rejected(self):
        recs = yi.extract_iocs("badexample.zzz")
        self.assertNotIn("badexample.zzz", values_of(recs, "domain"))

    def test_domain_numeric_tld_rejected(self):
        recs = yi.extract_iocs("1.2.3.44")
        self.assertNotIn("1.2.3.44", values_of(recs, "domain"))

    def test_domain_subdomain_full_fqdn(self):
        recs = yi.extract_iocs("cdn.evil.example.com")
        self.assertIn("cdn.evil.example.com", values_of(recs, "domain"))

    def test_domain_single_label_rejected(self):
        recs = yi.extract_iocs("localhost 服务")
        self.assertNotIn("localhost", values_of(recs, "domain"))

    def test_domain_not_extracted_inside_email(self):
        recs = yi.extract_iocs("admin@example.com")
        self.assertNotIn("example.com", values_of(recs, "domain"))
        self.assertIn("admin@example.com", values_of(recs, "email"))

    def test_domain_hyphen_label(self):
        recs = yi.extract_iocs("my-site.example.com")
        self.assertIn("my-site.example.com", values_of(recs, "domain"))

    def test_domain_cc_tld(self):
        recs = yi.extract_iocs("shop.example.cn")
        self.assertIn("shop.example.cn", values_of(recs, "domain"))

class TestURL(unittest.TestCase):
    def test_url_basic(self):
        recs = yi.extract_iocs("http://example.com/a")
        self.assertIn("http://example.com/a", values_of(recs, "url"))

    def test_url_https(self):
        recs = yi.extract_iocs("https://example.com/a")
        self.assertIn("https://example.com/a", values_of(recs, "url"))

    def test_url_default_port_stripped(self):
        recs = yi.extract_iocs("http://example.com:80/x")
        self.assertIn("http://example.com/x", values_of(recs, "url"))

    def test_url_nondefault_port_kept(self):
        recs = yi.extract_iocs("http://example.com:8080/x")
        self.assertIn("http://example.com:8080/x", values_of(recs, "url"))

    def test_url_fragment_dropped(self):
        recs = yi.extract_iocs("http://example.com/a#section")
        self.assertIn("http://example.com/a", values_of(recs, "url"))

    def test_url_query_kept(self):
        recs = yi.extract_iocs("http://example.com/a?id=1&x=2")
        self.assertIn("http://example.com/a?id=1&x=2", values_of(recs, "url"))

    def test_url_case_normalized(self):
        recs = yi.extract_iocs("HTTP://EXAMPLE.COM/A")
        self.assertIn("http://example.com/A", values_of(recs, "url"))

    def test_url_trailing_punct_stripped(self):
        recs = yi.extract_iocs("(https://example.com/a).")
        self.assertIn("https://example.com/a", values_of(recs, "url"))

    def test_url_cjk_punct_stops(self):
        recs = yi.extract_iocs("http://example.com/a，链接")
        self.assertIn("http://example.com/a", values_of(recs, "url"))

    def test_url_ip_host(self):
        recs = yi.extract_iocs("http://1.2.3.4/x")
        self.assertIn("http://1.2.3.4/x", values_of(recs, "url"))
        self.assertIn("1.2.3.4", values_of(recs, "ipv4"))

    def test_url_ipv6_host(self):
        recs = yi.extract_iocs("http://[2001:db8::1]/x")
        self.assertIn("http://[2001:db8::1]/x", values_of(recs, "url"))

    def test_url_defanged_url(self):
        recs = yi.extract_iocs("hxxp://bad[.]com/a")
        self.assertIn("http://bad.com/a", values_of(recs, "url"))

    def test_url_invalid_scheme_rejected(self):
        recs = yi.extract_iocs("file:///etc/passwd")
        self.assertNotIn("file:///etc/passwd", values_of(recs, "url"))

    def test_url_userinfo_defanged(self):
        recs = yi.extract_iocs("http://user:pass@example.com/a")
        self.assertIn("http://user:pass@example.com/a", values_of(recs, "url"))
        url = [r for r in recs if r["type"] == "url"][0]
        self.assertIn("[@]", url["defanged"])


class TestEmail(unittest.TestCase):
    def test_email_basic(self):
        recs = yi.extract_iocs("联系 admin@example.com")
        self.assertIn("admin@example.com", values_of(recs, "email"))

    def test_email_uppercase_normalized(self):
        recs = yi.extract_iocs("Admin@Example.COM")
        self.assertIn("admin@example.com", values_of(recs, "email"))

    def test_email_dotted_user(self):
        recs = yi.extract_iocs("user.name@example.com")
        self.assertIn("user.name@example.com", values_of(recs, "email"))

    def test_email_no_domain_dot_rejected(self):
        recs = yi.extract_iocs("a@b 不是邮箱")
        self.assertNotIn("a@b", values_of(recs, "email"))

    def test_email_defanged(self):
        recs = yi.extract_iocs("admin[@]example[.]com")
        self.assertIn("admin@example.com", values_of(recs, "email"))


class TestHash(unittest.TestCase):
    MD5 = "44d88612fea8a8f36de82e1278abb02f"
    SHA1 = "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    SHA512 = ("cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce"
              "47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e")

    def test_hash_md5(self):
        recs = yi.extract_iocs(self.MD5)
        self.assertIn(self.MD5, values_of(recs, "hash"))

    def test_hash_sha1(self):
        recs = yi.extract_iocs(self.SHA1)
        self.assertIn(self.SHA1, values_of(recs, "hash"))

    def test_hash_sha256(self):
        recs = yi.extract_iocs(self.SHA256)
        self.assertIn(self.SHA256, values_of(recs, "hash"))

    def test_hash_sha512(self):
        recs = yi.extract_iocs(self.SHA512)
        self.assertIn(self.SHA512, values_of(recs, "hash"))

    def test_hash_uppercase_normalized(self):
        recs = yi.extract_iocs(self.MD5.upper())
        self.assertIn(self.MD5, values_of(recs, "hash"))

    def test_hash_unknown_length_rejected(self):
        recs = yi.extract_iocs("ab" * 24)
        self.assertEqual(values_of(recs, "hash"), [])

    def test_hash_uuid_not_matched(self):
        recs = yi.extract_iocs("550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(values_of(recs, "hash"), [])

    def test_hash_label_md5(self):
        recs = yi.extract_iocs("MD5: " + self.MD5)
        self.assertIn(self.MD5, values_of(recs, "hash"))


class TestCVE(unittest.TestCase):
    def test_cve_basic(self):
        recs = yi.extract_iocs("CVE-2024-1234")
        self.assertIn("CVE-2024-1234", values_of(recs, "cve"))

    def test_cve_lowercase_normalized(self):
        recs = yi.extract_iocs("cve-2024-12345")
        self.assertIn("CVE-2024-12345", values_of(recs, "cve"))

    def test_cve_defanged_unchanged(self):
        recs = yi.extract_iocs("CVE-2024-1234")
        cve = [r for r in recs if r["type"] == "cve"][0]
        self.assertEqual(cve["defanged"], "CVE-2024-1234")


class TestDefangRefang(unittest.TestCase):
    def test_refang_dot_bracket(self):
        self.assertEqual(yi.refang_text("bad[.]com"), "bad.com")

    def test_refang_dot_paren(self):
        self.assertEqual(yi.refang_text("bad(.)com"), "bad.com")

    def test_refang_dot_word(self):
        self.assertEqual(yi.refang_text("bad[dot]com"), "bad.com")
        self.assertEqual(yi.refang_text("bad(DOT)com"), "bad.com")

    def test_refang_colon(self):
        self.assertEqual(yi.refang_text("1[:]2"), "1:2")

    def test_refang_at(self):
        self.assertEqual(yi.refang_text("user[@]example.com"), "user@example.com")

    def test_refang_hxxp(self):
        self.assertEqual(yi.refang_text("hxxp://a.com"), "http://a.com")
        self.assertEqual(yi.refang_text("hXXps://a.com"), "https://a.com")

    def test_refang_slash(self):
        self.assertEqual(yi.refang_text("a[/]b"), "a/b")

    def test_defang_value_ipv4(self):
        self.assertEqual(yi.defang_value("1.2.3.4", "ipv4"), "1[.]2[.]3[.]4")

    def test_defang_value_ipv6(self):
        self.assertEqual(yi.defang_value("2001:db8::1", "ipv6"), "2001[:]db8[:][:]1")

    def test_defang_value_domain(self):
        self.assertEqual(yi.defang_value("example.com", "domain"), "example[.]com")

    def test_defang_value_url(self):
        self.assertEqual(yi.defang_value("http://example.com/a", "url"),
                         "hxxp://example[.]com/a")

    def test_defang_value_email(self):
        self.assertEqual(yi.defang_value("a@b.com", "email"), "a[@]b[.]com")

    def test_roundtrip_extract_defang(self):
        recs = yi.extract_iocs("hxxp://bad[.]com/a")
        self.assertIn("http://bad.com/a", values_of(recs, "url"))
        url = [r for r in recs if r["type"] == "url"][0]
        self.assertEqual(url["defanged"], "hxxp://bad[.]com/a")

class TestExtract(unittest.TestCase):
    def test_extract_dedup_count(self):
        recs = yi.extract_iocs("203.0.113.5\n203.0.113.5")
        v = [r for r in recs if r["type"] == "ipv4"]
        self.assertEqual(len(v), 1)
        self.assertEqual(v[0]["count"], 2)

    def test_extract_first_line(self):
        recs = yi.extract_iocs("第一行\n第二行 evil.example.com")
        d = [r for r in recs if r["type"] == "domain"][0]
        self.assertEqual(d["first_line"], 2)

    def test_extract_min_count(self):
        text = "203.0.113.5\n203.0.113.5\n1.1.1.1"
        recs = yi.extract_iocs(text, min_count=2)
        v = values_of(recs, "ipv4")
        self.assertIn("203.0.113.5", v)
        self.assertNotIn("1.1.1.1", v)

    def test_extract_types_filter(self):
        recs = yi.extract_iocs("203.0.113.5 evil.example.com", types=["domain"])
        self.assertEqual(types_of(recs), ["domain"])

    def test_extract_snippet_context(self):
        recs = yi.extract_iocs("前文 203.0.113.5 后文")
        v = [r for r in recs if r["type"] == "ipv4"][0]
        self.assertIn("前文", v["snippet"])

    def test_extract_no_ioc(self):
        recs = yi.extract_iocs("没有任何指标的一行普通文字")
        self.assertEqual(recs, [])

    def test_extract_mixed_defanged_and_raw_dedup(self):
        recs = yi.extract_iocs("hxxp://a[.]com\nhttp://a.com")
        urls = values_of(recs, "url")
        self.assertEqual(len(urls), 1)
        self.assertEqual(urls[0], "http://a.com")

    def test_extract_line_keepends(self):
        text = "203.0.113.5\r\n1.1.1.1\r\n"
        recs = yi.extract_iocs(text)
        self.assertEqual(len(values_of(recs, "ipv4")), 2)

    def test_extract_hex_in_text_not_hash(self):
        recs = yi.extract_iocs("颜色是 #ff0000")
        self.assertEqual(values_of(recs, "hash"), [])


class TestOutputs(unittest.TestCase):
    def test_json_structure(self):
        recs = yi.extract_iocs("203.0.113.5")
        doc = json.loads(yi.build_json(recs, "2026-08-27T00:00:00+00:00", "test.txt"))
        self.assertEqual(doc["tool"], "yotta-intel")
        self.assertEqual(doc["summary"]["total"], 1)
        self.assertEqual(doc["indicators"][0]["value"], "203.0.113.5")

    def test_csv_columns(self):
        recs = yi.extract_iocs("203.0.113.5")
        text = yi.build_csv(recs)
        self.assertTrue(text.startswith("type,value,defanged,count,first_line,snippet"))
        self.assertIn("203.0.113.5", text)

    def test_stix_bundle(self):
        recs = yi.extract_iocs("203.0.113.5 evil.example.com")
        bundle = yi.build_stix(recs, "2026-08-27T00:00:00+00:00")
        self.assertEqual(bundle["type"], "bundle")
        self.assertEqual(bundle["spec_version"], "2.1")
        self.assertEqual(len(bundle["objects"]), 2)
        self.assertTrue(all(o["type"] == "indicator" for o in bundle["objects"]))

    def test_stix_pattern_ipv4(self):
        self.assertEqual(yi.stix_pattern("ipv4", "1.2.3.4"),
                         "[ipv4-addr:value = '1.2.3.4']")

    def test_stix_pattern_domain(self):
        self.assertEqual(yi.stix_pattern("domain", "example.com"),
                         "[domain-name:value = 'example.com']")

    def test_stix_pattern_hash_md5(self):
        self.assertEqual(yi.stix_pattern("hash", "ab" * 16),
                         "[file:hashes.'MD5' = '%s']" % ("ab" * 16))

    def test_stix_pattern_hash_sha256(self):
        self.assertEqual(yi.stix_pattern("hash", "ab" * 32),
                         "[file:hashes.'SHA-256' = '%s']" % ("ab" * 32))

    def test_stix_uuid_deterministic(self):
        b1 = yi.build_stix(yi.extract_iocs("203.0.113.5"), "t")
        b2 = yi.build_stix(yi.extract_iocs("203.0.113.5"), "t")
        self.assertEqual(b1["objects"][0]["id"], b2["objects"][0]["id"])

    def test_text_output(self):
        recs = yi.extract_iocs("203.0.113.5")
        out = yi.build_text(recs)
        self.assertIn("203.0.113.5", out)
        self.assertIn("defang", out)

    def test_text_output_empty(self):
        out = yi.build_text([])
        self.assertIn("未发现", out)

    def test_defang_stream(self):
        out = yi.defang_text("访问 http://example.com/a")
        self.assertIn("hxxp://example[.]com/a", out)

    def test_refang_stream(self):
        out = yi.refang_text("hxxp://example[.]com/a")
        self.assertIn("http://example.com/a", out)


class TestCLI(unittest.TestCase):
    def test_cli_extract_stdin_exit1(self):
        r = run_cli("extract", "--stdin", stdin="203.0.113.5")
        self.assertEqual(r.returncode, 1)
        self.assertIn("203.0.113.5", r.stdout)

    def test_cli_extract_no_ioc_exit0(self):
        r = run_cli("extract", "--stdin", stdin="没有指标")
        self.assertEqual(r.returncode, 0)

    def test_cli_json_output(self):
        r = run_cli("extract", "--stdin", "--format", "json", stdin="1.2.3.4")
        doc = json.loads(r.stdout)
        self.assertEqual(doc["indicators"][0]["type"], "ipv4")

    def test_cli_csv_output(self):
        r = run_cli("extract", "--stdin", "--format", "csv", stdin="1.2.3.4")
        self.assertTrue(r.stdout.startswith("type,value"))

    def test_cli_stix_output(self):
        r = run_cli("extract", "--stdin", "--format", "stix", stdin="1.2.3.4")
        doc = json.loads(r.stdout)
        self.assertEqual(doc["type"], "bundle")

    def test_cli_output_file(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "out.json")
            r = run_cli("extract", "--stdin", "--format", "json", "--output", out,
                        stdin="1.2.3.4")
            self.assertEqual(r.returncode, 1)
            doc = json.loads(io.open(out, encoding="utf-8").read())
            self.assertEqual(doc["indicators"][0]["value"], "1.2.3.4")

    def test_cli_defang(self):
        r = run_cli("defang", "--stdin", stdin="http://a.com")
        self.assertEqual(r.returncode, 0)
        self.assertIn("hxxp://a[.]com", r.stdout)

    def test_cli_refang(self):
        r = run_cli("refang", "--stdin", stdin="hxxp://a[.]com")
        self.assertEqual(r.returncode, 0)
        self.assertIn("http://a.com", r.stdout)

    def test_cli_version(self):
        r = run_cli("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("0.1.0", r.stdout)

    def test_cli_unknown_type_exit4(self):
        r = run_cli("extract", "--stdin", "--types", "bogus", stdin="1.2.3.4")
        self.assertEqual(r.returncode, 4)

    def test_cli_missing_input_exit4(self):
        r = run_cli("extract")
        self.assertEqual(r.returncode, 4)

    def test_cli_bad_path_exit4(self):
        r = run_cli("extract", "--path", os.path.join(tempfile.gettempdir(), "no-such-file-xyz"))
        self.assertEqual(r.returncode, 4)

    def test_cli_min_count(self):
        r = run_cli("extract", "--stdin", "--min-count", "2", stdin="1.1.1.1\n1.1.1.1\n2.2.2.2")
        self.assertIn("1.1.1.1", r.stdout)
        self.assertNotIn("2.2.2.2", r.stdout)

    def test_cli_path_file(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "intel.txt")
            io.open(src, "w", encoding="utf-8").write("evil.example.com")
            r = run_cli("extract", "--path", src)
            self.assertEqual(r.returncode, 1)
            self.assertIn("evil.example.com", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
