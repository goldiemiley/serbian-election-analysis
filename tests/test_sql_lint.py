"""Static guards on the SQL text. They exist because the DuckDB stand-in is more permissive than BigQuery in some places and
stricter in others; these rules keep the files inside the intersection and catch classic BigQuery rejections early."""
import pathlib
import re

import pytest

SQL = sorted((pathlib.Path(__file__).resolve().parents[1] / 'sql').glob('*.sql'))
# BigQuery reserved words that must not be used as unquoted aliases
RESERVED = {'all', 'and', 'any', 'array', 'as', 'asc', 'assert_rows_modified', 'at', 'between', 'by', 'case', 'cast', 'collate', 'contains',
            'create', 'cross', 'cube', 'current', 'default', 'define', 'desc', 'distinct', 'else', 'end', 'enum', 'escape', 'except',
            'exclude', 'exists', 'extract', 'false', 'fetch', 'following', 'for', 'from', 'full', 'group', 'grouping', 'groups', 'hash',
            'having', 'if', 'ignore', 'in', 'inner', 'intersect', 'interval', 'into', 'is', 'join', 'lateral', 'left', 'like', 'limit',
            'lookup', 'merge', 'natural', 'new', 'no', 'not', 'null', 'nulls', 'of', 'on', 'or', 'order', 'outer', 'over', 'partition',
            'preceding', 'proto', 'qualify', 'range', 'recursive', 'respect', 'right', 'rollup', 'rows', 'select', 'set', 'some', 'struct',
            'tablesample', 'then', 'to', 'treat', 'true', 'unbounded', 'union', 'unnest', 'using', 'when', 'where', 'window', 'with', 'within'}
FORBIDDEN = [r'\bCOUNTIF\s*\(', r'\bSAFE_CAST\s*\(', r'\bIN\s+UNNEST\s*\(', r'\bLOGICAL_OR\s*\(', r'\bLOGICAL_AND\s*\(']
TYPE_WORDS = [r'\bSTRING\b', r'\bINT64\b', r'\bFLOAT64\b']


def _strip(sql):
    return re.sub(r'--[^\n]*', '', sql)


@pytest.mark.parametrize('path', SQL, ids=lambda p: p.name)
def test_single_statement_and_header(path):
    raw = path.read_text()
    body = _strip(raw).strip().rstrip(';')
    literal_free = re.sub(r"'[^']*'", "''", body)
    assert ';' not in literal_free, 'more than one statement'
    assert raw.lstrip().startswith('-- STAGE'), 'file must start with a STAGE header comment (objective, input, output)'
    for tag in ('Objective', 'Input', 'Output'):
        assert tag in raw.split('CREATE')[0] or tag in raw[:2500], f'header lacks {tag}'


@pytest.mark.parametrize('path', SQL, ids=lambda p: p.name)
def test_no_reserved_word_aliases(path):
    body = re.sub(r"'[^']*'", "''", _strip(path.read_text()))
    for m in re.finditer(r'\bAS\s+([A-Za-z_][A-Za-z0-9_]*)', body):
        word = m.group(1).lower()
        # `CAST(x AS FLOAT64)` is a type, not an alias
        if word in {'float64', 'int64', 'string', 'date', 'timestamp', 'bool', 'numeric'}:
            continue
        if word in {'with', 'select'}:          # CREATE ... AS WITH / AS SELECT is a statement form, not an alias
            continue
        assert word not in RESERVED, f'reserved word used as alias: {m.group(0)}'


def _same_depth_block(body, pos):
    """Text of the query block (same parenthesis depth) that ends at `pos`, from its own SELECT."""
    depth, i = 0, pos - 1
    while i >= 0:
        ch = body[i]
        if ch == ')':
            depth += 1
        elif ch == '(':
            if depth == 0:
                break
            depth -= 1
        i -= 1
    seg = body[i + 1:pos]
    # drop nested parentheses so only this block's own clauses remain
    flat, d = [], 0
    for ch in seg:
        if ch == '(':
            d += 1
        elif ch == ')':
            d -= 1
        elif d == 0:
            flat.append(ch)
    return ''.join(flat)


@pytest.mark.parametrize('path', SQL, ids=lambda p: p.name)
def test_qualify_has_where_or_group(path):
    body = re.sub(r"'[^']*'", "''", _strip(path.read_text()))
    for m in re.finditer(r'\bQUALIFY\b', body):
        block = _same_depth_block(body, m.start())
        assert re.search(r'\b(WHERE|GROUP\s+BY|HAVING)\b', block), f'QUALIFY without WHERE/GROUP BY/HAVING in its own query block (position {m.start()})'


@pytest.mark.parametrize('path', SQL, ids=lambda p: p.name)
def test_portable_subset_only(path):
    body = re.sub(r"'[^']*'", "''", _strip(path.read_text()))
    for pat in FORBIDDEN:
        assert not re.search(pat, body, re.I), f'not in the portable subset: {pat}'


@pytest.mark.parametrize('path', SQL, ids=lambda p: p.name)
def test_type_words_not_inside_string_literals(path):
    """The DuckDB harness rewrites type words textually; keep them out of literals so the stand-in and BigQuery see the same text."""
    for lit in re.findall(r"'([^']*)'", _strip(path.read_text())):
        for pat in TYPE_WORDS:
            assert not re.search(pat, lit), f'type word inside a string literal: {lit!r}'


@pytest.mark.parametrize('path', SQL, ids=lambda p: p.name)
def test_tables_use_dataset_placeholder(path):
    body = _strip(path.read_text())
    for ref in re.findall(r'`([^`]+)`', body):
        assert ref.startswith('{DS}.'), f'table reference not parameterised with {{DS}}: {ref}'


@pytest.mark.parametrize('path', SQL, ids=lambda p: p.name)
def test_no_electoral_constants(path):
    """No municipality names, list names, party names or poll numbers typed into SQL (the task's strict coding rule)."""
    body = re.sub(r"'[^']*'", lambda m: m.group(0), _strip(path.read_text()))
    lits = re.findall(r"'([^']*)'", body)
    bad = re.compile(r'\b(vucic|vučić|dacic|dačić|sns|sps|srce|student|beograd|belgrade|novi sad|nis|niš)\b', re.I)
    for lit in lits:
        assert not bad.search(lit), f'electoral name inside a string literal: {lit!r}'


# ---------------------------------------------------------------------------------------------------- JOIN ... ON rules
_ON_END = re.compile(r'\b(JOIN|LEFT|RIGHT|INNER|CROSS|FULL|WHERE|GROUP|ORDER|QUALIFY|HAVING|UNION|LIMIT|WINDOW)\b', re.I)


def _join_conditions(body):
    """Yield the text of every `ON <condition>` clause: from ON to the next clause keyword at the same parenthesis depth, or to the
    parenthesis that closes the enclosing query block."""
    for m in re.finditer(r'\bON\b', body):
        depth, i, start = 0, m.end(), m.end()
        while i < len(body):
            ch = body[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0:
                k = _ON_END.match(body, i)
                if k and (i == 0 or not re.match(r'\w', body[i - 1])):
                    break
            i += 1
        yield body[start:i]


def _subquery_in_join_condition(sql):
    body = re.sub(r"'[^']*'", "''", _strip(sql))
    return [c.strip() for c in _join_conditions(body) if re.search(r'\(\s*(SELECT|WITH)\b', c, re.I)]


@pytest.mark.parametrize('path', SQL, ids=lambda p: p.name)
def test_no_subquery_inside_join_condition(path):
    """BigQuery rejects `JOIN ... ON x IN (SELECT ...)` ("IN subquery is not supported inside join predicate"); DuckDB accepts it.
    Select the rows in a CTE or subquery first and join to that."""
    bad = _subquery_in_join_condition(path.read_text())
    assert not bad, f'subquery inside a JOIN condition (BigQuery rejects this): {bad[0][:200]}'


def test_join_condition_rule_catches_the_known_failure():
    """The rule must fire on the exact construct BigQuery rejected in a real run, and stay quiet on the accepted rewrite."""
    old = ("SELECT 1 FROM `{DS}.a` AS p LEFT JOIN `{DS}.b` AS u ON u.geo_id = p.geo_id "
           "AND u.election_id IN (SELECT election_id FROM base_election) ORDER BY p.geo_id")
    new = ("WITH base_votes AS (SELECT u.geo_id FROM `{DS}.b` AS u WHERE u.election_id IN (SELECT election_id FROM base_election)) "
           "SELECT 1 FROM `{DS}.a` AS p LEFT JOIN base_votes AS u ON u.geo_id = p.geo_id ORDER BY p.geo_id")
    exists = "SELECT 1 FROM a JOIN b ON a.k = b.k AND EXISTS (SELECT 1 FROM c WHERE c.k = a.k)"
    in_parens = "SELECT 1 FROM a JOIN (SELECT k FROM b) AS bb ON a.k = bb.k WHERE a.x IN (SELECT 1)"
    assert _subquery_in_join_condition(old)
    assert _subquery_in_join_condition(exists)
    assert not _subquery_in_join_condition(new)
    assert not _subquery_in_join_condition(in_parens)
