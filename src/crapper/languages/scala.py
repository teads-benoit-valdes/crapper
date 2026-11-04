"""Scala 2 and Scala 3 methods and cyclomatic complexity.

Decision points are `if`, `while`, `do ... while`, `for`, each `case` clause
(match arms, `catch` cases, and partial functions), each guard (`case x if`
and `for (x <- xs if ...)`), and `&&` / `||`, which Scala parses as infix
expressions. Braced and indentation-based code give the same nodes, so Scala 3
syntax needs no extra rules. Nested defs, lambdas, and anonymous classes are
part of the def that contains them, so only a member of a class, object, trait,
package object, enum, or named given, an extension method, or a top-level def
is an entry. Abstract members have no body and are not entries.
Methods are namespaced by the package and the enclosing types
(`pkg.Outer.Inner`) so uml-viewer can attach scores to that type. An anonymous
given has no name, so its methods get the enclosing namespace.
"""

from crapper.languages.treesitter import (
    child_of_type,
    complexity,
    node_text,
    parse,
    start_line,
)
from crapper.model import Function

_DECISIONS = {
    "if_expression",
    "while_expression",
    "do_while_expression",
    "for_expression",
    "case_clause",
    "guard",
}
_LOGIC = {"&&", "||"}
_TYPES = {
    "class_definition",
    "object_definition",
    "trait_definition",
    "package_object",
    "enum_definition",
    "given_definition",
}
_NAME_TYPES = {"identifier", "operator_identifier"}


def _is_logic(data: bytes, node) -> bool:
    if node.type != "infix_expression":
        return False
    operator = child_of_type(node, "operator_identifier")
    return operator is not None and node_text(data, operator) in _LOGIC


def _name(data: bytes, node) -> str | None:
    ident = child_of_type(node, *_NAME_TYPES)
    return node_text(data, ident) if ident is not None else None


def _package(data: bytes, node) -> str | None:
    ident = child_of_type(node, "package_identifier")
    return node_text(data, ident) if ident is not None else None


def _leading_packages(data: bytes, root) -> list[str]:
    """`package a` lines that precede the code. They are siblings, not parents."""

    found = []
    for child in root.children:
        if child.type == "package_clause" and child_of_type(child, "template_body") is None:
            name = _package(data, child)
            if name:
                found.append(name)
    return found


def _enclosing(data: bytes, node) -> list[str]:
    names: list[str] = []
    current = node.parent
    while current is not None:
        if current.type == "package_clause":
            names.append(_package(data, current) or "")
        elif current.type in _TYPES:
            names.append(_name(data, current) or "")
        current = current.parent
    names.reverse()
    return names


def _end_line(data: bytes, node) -> int:
    """Last line of the code.

    A body on the next line without braces makes tree-sitter run the def up
    to where the next member starts, so trailing whitespace is dropped.
    """

    code = data[node.start_byte : node.end_byte].rstrip()
    return start_line(node) + code.count(b"\n")


def _record(data: bytes, node, leading: list[str], path: str) -> Function | None:
    if node.type != "function_definition":
        return None
    return Function(
        name=_name(data, node),
        namespace=".".join(part for part in [*leading, *_enclosing(data, node)] if part),
        complexity=complexity(
            node,
            lambda item: item.type in _DECISIONS or _is_logic(data, item),
            lambda _item: False,
        ),
        start_line=start_line(node),
        end_line=_end_line(data, node),
        path=path,
        language="scala",
    )


def functions_in_source(
    source: str, path: str, project_root: str | None = None
) -> list[Function]:
    del project_root
    data, tree = parse(source, "scala")
    leading = _leading_packages(data, tree.root_node)
    found: list[Function] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        recorded = _record(data, node, leading, path)
        if recorded is not None:
            found.append(recorded)
            continue
        stack.extend(reversed(node.children))
    return found
