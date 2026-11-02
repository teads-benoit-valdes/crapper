from crapper.languages.scala2 import functions_in_source

SCORE = """
class Sample {
  def score(a: Boolean, b: Boolean, xs: List[Int]): Int = {
    for (x <- xs if x > 0) { println(x) }
    while (a) { }
    do { } while (b)
    if (a && b || xs.isEmpty) 1 else 2
    xs match {
      case Nil => 0
      case h :: _ if h > 0 => h
      case _ => 3
    }
    try { 1 } catch { case _: RuntimeException => 2 }
  }
}
"""

NESTED = """
class Sample {
  def outer(xs: List[Int]): List[Int] = {
    def keep(x: Int): Boolean = if (x > 0) true else false
    xs.filter(x => if (x > 1) keep(x) else false)
  }

  def anonymous(): Runnable = new Runnable {
    def run(): Unit = if (true) println("x")
  }

  def partial(xs: List[Int]): List[Int] = xs.collect { case 1 => 1; case 2 => 2 }
}
"""

PACKAGES = """
package demo.pkg
package inner

package object util {
  def helper(x: Int): Int = x
}

trait Shape {
  def area: Double
  def describe(): String = "shape"
}

object Ops {
  def +(other: Int): Int = other
  class Inner {
    def tick(): Int = 1
  }
}
"""

BRACED = """
package outer {
  package nested {
    class C {
      def f(x: Int): Int = if (x > 0) 1 else 0
    }
  }
}
"""

ADJACENT = """object A {
  def one(x: Int): Int =
    if (x > 0) 1 else 0
  def two = 2

  def three(x: Int) =
    x + 1

  def four = 4
}
"""


def _summary(functions):
    return [(fn.namespace, fn.name, fn.complexity) for fn in functions]


def test_counts_loops_guards_cases_and_logic():
    functions = functions_in_source(SCORE, "Sample.scala")
    assert _summary(functions) == [("Sample", "score", 13)]
    assert functions[0].language == "scala2"
    assert functions[0].path == "Sample.scala"


def test_nested_defs_lambdas_and_anonymous_classes_belong_to_the_enclosing_def():
    functions = functions_in_source(NESTED, "Sample.scala")
    assert _summary(functions) == [
        ("Sample", "outer", 3),
        ("Sample", "anonymous", 2),
        ("Sample", "partial", 3),
    ]


def test_namespaces_follow_packages_and_enclosing_types():
    functions = functions_in_source(PACKAGES, "src/main/scala/demo/Shapes.scala")
    assert _summary(functions) == [
        ("demo.pkg.inner.util", "helper", 1),
        ("demo.pkg.inner.Shape", "describe", 1),
        ("demo.pkg.inner.Ops", "+", 1),
        ("demo.pkg.inner.Ops.Inner", "tick", 1),
    ]


def test_braced_packages_nest():
    functions = functions_in_source(BRACED, "C.scala")
    assert _summary(functions) == [("outer.nested.C", "f", 2)]


def test_abstract_methods_and_class_bodies_are_not_entries():
    source = """
    abstract class Base {
      val ready = if (System.nanoTime() > 0) 1 else 0
      def abstractOne(): Int
      def concrete(): Int = 1
    }
    """
    assert _summary(functions_in_source(source, "Base.scala")) == [("Base", "concrete", 1)]


def test_a_def_ends_on_its_last_line_not_where_the_next_one_starts():
    functions = functions_in_source(ADJACENT, "A.scala")
    assert [(fn.name, fn.start_line, fn.end_line) for fn in functions] == [
        ("one", 2, 3),
        ("two", 4, 4),
        ("three", 6, 7),
        ("four", 9, 9),
    ]


def test_end_line_is_right_after_multibyte_characters():
    source = 'object A {\n  def greet(x: Int) =\n    "héllo ✓" + x\n  def next = 1\n}\n'
    functions = functions_in_source(source, "A.scala")
    assert [(fn.name, fn.start_line, fn.end_line) for fn in functions] == [
        ("greet", 2, 3),
        ("next", 4, 4),
    ]


def test_keywords_in_comments_and_strings_are_not_decisions():
    source = '''
    object A {
      def stable(): String = {
        val text = "if && || case while for"
        // if && || case while for
        /* if && || case while for */
        text
      }
    }
    '''
    assert _summary(functions_in_source(source, "A.scala")) == [("A", "stable", 1)]


def test_operators_other_than_logic_are_not_decisions():
    source = "object A { def f(a: Int, b: Int): Boolean = a > b & a < 3 | a == b }\n"
    assert _summary(functions_in_source(source, "A.scala")) == [("A", "f", 1)]


def test_top_level_file_without_a_package_has_the_type_as_namespace():
    functions = functions_in_source("object Main { def main(args: Array[String]): Unit = () }\n", "Main.scala")
    assert _summary(functions) == [("Main", "main", 1)]
