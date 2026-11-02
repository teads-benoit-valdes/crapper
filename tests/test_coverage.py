from crapper.coverage import (
    CoverageBundle,
    go_percent,
    load_bundle,
    parse_cobertura,
    parse_form_coverage,
    parse_go_profile,
    parse_jacoco_index,
    parse_lcov,
)
from crapper.model import Function


def function(**kwargs):
    defaults = dict(
        name="choose",
        namespace="demo.core",
        complexity=2,
        start_line=3,
        end_line=5,
        path="src/demo/core.clj",
        language="clojure",
        jacoco_class=None,
    )
    defaults.update(kwargs)
    return Function(**defaults)


def test_cloverage_form_counts_and_lcov_lines():
    html = '<span class="pc" title="1 out of 2 forms covered">   4&nbsp;&nbsp;(if x 1)</span>'
    assert parse_form_coverage(html) == {4: (1, 2)}
    lcov = "SF:src/demo/core.clj\nDA:3,1\nDA:4,0\nDA:9,3\nend_of_record\n"
    parsed = parse_lcov(lcov)
    bundle = CoverageBundle(lcov=parsed, form_html={"src/demo/core.clj": {4: (1, 2)}})
    # Form HTML wins over LCOV for Clojure, matching crap4clj.
    assert bundle.percent_for(function(start_line=3, end_line=5)) == 50.0


def test_lcov_percentage_when_there_is_no_html():
    lcov = parse_lcov("SF:src/demo/core.clj\nDA:3,1\nDA:4,0\nend_of_record\n")
    bundle = CoverageBundle(lcov=lcov)
    assert bundle.percent_for(function(start_line=3, end_line=4)) == 50.0
    assert bundle.percent_for(function(path="src/missing.clj")) is None


def test_lcov_branch_records_override_line_hits():
    text = "SF:src/demo/app.ts\nDA:2,1\nDA:3,1\nBRDA:3,0,0,1\nBRDA:3,0,1,-\nend_of_record\n"
    parsed = parse_lcov(text)
    assert parsed["src/demo/app.ts"][2] == (1, 1)
    assert parsed["src/demo/app.ts"].branches[3] == (1, 2)
    bundle = CoverageBundle(lcov=parsed)
    scored = function(
        path="src/demo/app.ts",
        language="typescript",
        start_line=2,
        end_line=3,
        namespace="demo.app",
    )
    assert bundle.percent_for(scored) == 50.0


def test_a_branchless_span_keeps_line_coverage():
    text = "SF:src/demo/app.ts\nDA:2,1\nDA:3,0\nBRDA:8,0,0,1\nBRDA:8,0,1,0\nend_of_record\n"
    bundle = CoverageBundle(lcov=parse_lcov(text))
    scored = function(path="src/demo/app.ts", language="typescript", start_line=2, end_line=3)
    assert bundle.percent_for(scored) == 50.0


def test_go_profile_matches_crap4go_statement_ranges():
    profile = parse_go_profile(
        "mode: set\ngithub.com/acme/demo/board.go:4.1,6.2 2 1\ngithub.com/acme/demo/board.go:8.1,9.2 1 0\n"
    )
    assert go_percent(profile, "board.go", 4, 6) == 100.0
    assert go_percent(profile, "board.go", 8, 9) == 0.0
    assert go_percent(profile, "other.go", 1, 3) is None


def test_jacoco_instruction_coverage_joins_on_class_and_method():
    xml = """<?xml version="1.0"?>
    <report>
      <package>
        <class name="demo/pkg/Board">
          <method name="place" line="4">
            <counter type="INSTRUCTION" missed="1" covered="3"/>
          </method>
        </class>
        <class name="demo/pkg/Board$Inner">
          <method name="tick" line="9">
            <counter type="INSTRUCTION" missed="0" covered="2"/>
          </method>
        </class>
      </package>
    </report>
    """
    bundle = CoverageBundle(jacoco=parse_jacoco_index(xml))
    outer = function(
        name="place",
        namespace="demo.pkg.Board",
        language="java",
        jacoco_class="demo.pkg.Board",
        start_line=4,
        path="src/demo/pkg/Board.java",
    )
    inner = function(
        name="tick",
        namespace="demo.pkg.Board.Inner",
        language="java",
        jacoco_class="demo.pkg.Board$Inner",
        start_line=9,
        path="src/demo/pkg/Board.java",
    )
    assert bundle.percent_for(outer) == 75.0
    assert bundle.percent_for(inner) == 100.0


def test_jacoco_skips_methods_without_an_instruction_counter():
    xml = """<report>
      <class name="demo/pkg/Board">
        <method name="skip" line="2">
          <counter type="LINE" missed="1" covered="0"/>
        </method>
        <method name="bad" line="nope">
          <counter type="INSTRUCTION" missed="1" covered="1"/>
        </method>
        <counter type="INSTRUCTION" missed="0" covered="1"/>
      </class>
    </report>"""
    found = parse_jacoco_index(xml)
    assert list(found) == ["demo.pkg.Board#bad"]
    assert found["demo.pkg.Board#bad"][0].line == 0


def test_missing_go_profile_is_na():
    assert go_percent(None, "board.go", 1, 3) is None


def test_load_bundle_merges_each_report(tmp_path):
    lcov = tmp_path / "target" / "coverage" / "lcov.info"
    lcov.parent.mkdir(parents=True)
    lcov.write_text("SF:src/demo/core.clj\nDA:3,1\nDA:4,0\nend_of_record\n", encoding="utf-8")
    go = tmp_path / "target" / "coverage" / "go" / "coverage.out"
    go.parent.mkdir(parents=True)
    go.write_text("mode: set\nboard.go:1.1,2.2 1 1\n", encoding="utf-8")
    jacoco = tmp_path / "target" / "site" / "jacoco" / "jacoco.xml"
    jacoco.parent.mkdir(parents=True)
    jacoco.write_text(
        '<report><class name="demo/Board"><method name="place" line="4">'
        '<counter type="INSTRUCTION" missed="0" covered="1"/></method></class></report>',
        encoding="utf-8",
    )
    html = tmp_path / "target" / "coverage" / "src" / "demo" / "core.clj.html"
    html.parent.mkdir(parents=True)
    html.write_text(
        '<span title="1 out of 2 forms covered">   4&nbsp;&nbsp;(if x 1)</span>',
        encoding="utf-8",
    )
    (tmp_path / "target" / "coverage" / "index.html").write_text("<html></html>", encoding="utf-8")
    bundle = load_bundle(tmp_path)
    assert bundle.percent_for(function(start_line=3, end_line=4)) == 50.0
    assert bundle.go_profile is not None
    assert bundle.jacoco is not None


COBERTURA = """<?xml version="1.0"?>
<!DOCTYPE coverage SYSTEM "https://cobertura.sourceforge.net/xml/coverage-04.dtd">
<coverage line-rate="0.5" version="1.0">
    <sources>
        <source>--source</source>
        <source>/proj/src/main/scala</source>
    </sources>
    <packages>
        <package name="demo">
            <classes>
                <class name="demo.Calc" filename="demo/Calc.scala">
                    <methods>
                        <method name="demo/Calc/classify" signature="()V">
                            <lines>
                                <line number="7" hits="0" branch="false"/>
                                <line number="7" hits="0" branch="false"/>
                            </lines>
                        </method>
                    </methods>
                    <lines>
                        <line number="6" hits="1" branch="false"/>
                        <line number="6" hits="0" branch="true"/>
                        <line number="7" hits="2" branch="false"/>
                        <line number="9" hits="0" branch="false"/>
                    </lines>
                </class>
                <class name="demo.Calc$" filename="demo/Calc.scala">
                    <methods/>
                    <lines>
                        <line number="12" hits="1" branch="false"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>
"""


def scala_function(**kwargs):
    defaults = dict(
        name="classify",
        namespace="demo.Calc",
        start_line=6,
        end_line=9,
        path="src/main/scala/demo/Calc.scala",
        language="scala2",
    )
    defaults.update(kwargs)
    return function(**defaults)


def test_cobertura_counts_statements_per_line_from_the_class_lines():
    parsed = parse_cobertura(COBERTURA)
    assert list(parsed) == ["/proj/src/main/scala/demo/Calc.scala"]
    record = parsed["/proj/src/main/scala/demo/Calc.scala"]
    # Method-level lines repeat the class lines and must not be counted twice.
    assert dict(record) == {6: (1, 2), 7: (1, 1), 9: (0, 1), 12: (1, 1)}
    # scoverage branch="true" marks a branch body, not a taken/not-taken pair.
    assert record.branches == {}


def test_cobertura_picks_the_source_dir_that_holds_the_file(tmp_path):
    real = tmp_path / "core" / "src" / "main" / "scala"
    (real / "demo").mkdir(parents=True)
    (real / "demo" / "Calc.scala").write_text("object Calc\n", encoding="utf-8")
    text = COBERTURA.replace("/proj/src/main/scala", f"/elsewhere</source><source>{real}")
    parsed = parse_cobertura(text)
    assert list(parsed) == [(real / "demo" / "Calc.scala").as_posix()]


def test_cobertura_without_an_absolute_source_dir_keeps_the_relative_name():
    text = COBERTURA.replace("/proj/src/main/scala", "src/main/scala")
    assert list(parse_cobertura(text)) == ["demo/Calc.scala"]


def test_scala_coverage_is_the_statement_ratio_over_the_function_lines():
    bundle = CoverageBundle(lcov=parse_cobertura(COBERTURA))
    # Lines 6-9: 2 of 4 statements ran.
    assert bundle.percent_for(scala_function()) == 50.0
    assert bundle.percent_for(scala_function(start_line=9, end_line=9)) == 0.0
    assert bundle.percent_for(scala_function(path="src/main/scala/demo/Other.scala")) is None


def test_load_bundle_reads_scoverage_reports_of_every_module(tmp_path):
    for report in (
        "target/scala-2.13/coverage-report/cobertura.xml",
        "core/target/scala-2.12/coverage-report/cobertura.xml",
        "libs/util/target/scala-2.13/coverage-report/cobertura.xml",
    ):
        path = tmp_path / report
        path.parent.mkdir(parents=True)
        module = report.split("/")[0]
        path.write_text(
            COBERTURA.replace("/proj/src/main/scala", f"/proj/{module}/src/main/scala"),
            encoding="utf-8",
        )
    elsewhere = tmp_path / "other" / "coverage" / "cobertura.xml"
    elsewhere.parent.mkdir(parents=True)
    elsewhere.write_text(COBERTURA, encoding="utf-8")
    bundle = load_bundle(tmp_path)
    assert sorted(bundle.lcov) == [
        "/proj/core/src/main/scala/demo/Calc.scala",
        "/proj/libs/src/main/scala/demo/Calc.scala",
        "/proj/target/src/main/scala/demo/Calc.scala",
    ]
