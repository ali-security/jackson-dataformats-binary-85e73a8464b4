#!/usr/bin/env python3
"""Print per-suite results, a total, and every skipped test with its reason,
read from the Maven surefire XML reports of all modules.

The build runs Maven quietly enough that surefire's own per-test output is not
enough to name skipped tests; a bare JUnit Assume skip only carries a Hamcrest
message ("got: <false>, expected: is <true>"), so for those the explanatory
comment that precedes the assumption in the test source is printed as well.
"""
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET

BARE = re.compile(r"^(got: <false>, expected: is <true>|got: <true>, expected: is <false>)?$")


def source_reason(classname, testname):
    rel = classname.replace(".", "/") + ".java"
    for path in glob.glob("*/src/test/java/" + rel):
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        # Prefer the assumption/annotation inside (or on) the skipped method,
        # then fall back to a class-wide one (e.g. in a @Before/@BeforeEach).
        start = 0
        for i, line in enumerate(lines):
            if re.search(r"\b%s\s*\(" % re.escape(testname), line):
                start = max(0, i - 3)
                break
        candidates = list(range(start, len(lines))) + list(range(0, start))
        for i in candidates:
            line = lines[i]
            if line.lstrip().startswith("import "):
                continue
            if re.search(r"\bassume(True|False|That)\s*\(|@Disabled|@Ignore", line):
                comments = []
                j = i - 1
                while j >= 0 and lines[j].strip().startswith("//"):
                    comments.insert(0, lines[j].strip().lstrip("/").strip())
                    j -= 1
                stmt = line.strip()
                k = i
                while not stmt.endswith((";", ")")) and k + 1 < len(lines) and k < i + 5:
                    k += 1
                    stmt += " " + lines[k].strip()
                text = " ".join(c for c in comments if c)
                return (text + " | " if text else "") + "source: " + stmt
    return ""


def main():
    reports = sorted(glob.glob("*/target/surefire-reports/TEST-*.xml"))
    total = fail = err = skip = 0
    skipped = []
    failed = []
    for rep in reports:
        root = ET.parse(rep).getroot()
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        for s in suites:
            t = int(s.get("tests", 0))
            f = int(s.get("failures", 0))
            e = int(s.get("errors", 0))
            k = int(s.get("skipped", 0))
            total += t
            fail += f
            err += e
            skip += k
            mod = rep.split(os.sep)[0]
            print("SUITE [%s] %s: run=%d passed=%d failures=%d errors=%d skipped=%d"
                  % (mod, s.get("name"), t, t - f - e - k, f, e, k))
            for tc in s.findall("testcase"):
                name = "%s.%s" % (tc.get("classname"), tc.get("name"))
                sk = tc.find("skipped")
                if sk is not None:
                    msg = (sk.get("message") or "").strip()
                    if BARE.match(msg):
                        extra = source_reason(tc.get("classname"), tc.get("name"))
                        msg = (msg + " -- " if msg else "") + (extra or "skipped by test assumption/annotation")
                    skipped.append("SKIPPED: %s -- reason: %s" % (name, msg))
                for tag in ("failure", "error"):
                    x = tc.find(tag)
                    if x is not None:
                        failed.append("%s: %s -- %s" % (tag.upper(), name, (x.get("message") or "")[:300]))
    print("TEST SUMMARY: reports=%d Tests run=%d, Passed=%d, Failures=%d, Errors=%d, Skipped=%d"
          % (len(reports), total, total - fail - err - skip, fail, err, skip))
    for line in skipped:
        print(line)
    for line in failed:
        print(line)
    if not reports:
        print("TEST SUMMARY: no surefire reports found")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
