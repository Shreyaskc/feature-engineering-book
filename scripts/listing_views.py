"""Render and validate canonical listing views without executing lesson code."""
from __future__ import annotations
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re


def canonical_listings(root):
    records = []
    for suite in ['chapters01_02'] + [f'chapter{n:02}' for n in range(3, 11)]:
        registry = root/suite/'printed_snippets.json'
        if registry.exists():
            items = json.loads(registry.read_text())
            items = items['snippets'] if isinstance(items, dict) else items
            for item in items:
                records.append({'suite':suite, 'id':item['id'], 'title':item.get('title',item['id']),
                                'chapter':item.get('chapter',int(suite[-2:]) if suite != 'chapters01_02' else None),
                                'source_path':str(registry.relative_to(root)),
                                'language':item.get('language','python'),'code':item['code'],
                                'expected_stdout':item.get('expected_stdout',item.get('stdout'))})
        else:
            source = root/suite/'printed_examples.py'
            text = source.read_text()
            if suite == 'chapter06':
                values = {}
                for node in ast.parse(text).body:
                    if isinstance(node,ast.Assign):
                        for target in node.targets:
                            if isinstance(target,ast.Name) and target.id in ('LISTINGS','LISTING_TITLES'):
                                values[target.id] = ast.literal_eval(node.value)
                items = zip(values['LISTING_TITLES'],values['LISTINGS'])
            else:
                matches = list(re.finditer(r'^# Listing (\d+)[.:] (.+)\n',text,re.MULTILINE))
                items = []
                for index,match in enumerate(matches):
                    end = matches[index+1].start() if index+1 < len(matches) else text.rfind("print('All ")
                    # Blank separators belong to the source; preserve them.
                    items.append((match[2],text[match.end():end]))
            for number,(title,code) in enumerate(items,1):
                records.append({'suite':suite,'id':f'listing_{number}','title':title,
                                'chapter':int(suite[-2:]),'source_path':str(source.relative_to(root)),
                                'language':'python','code':code,'expected_stdout':None})
    if len(records) != 72:
        raise ValueError(f'Expected 72 canonical listings, got {len(records)}')
    for item in records:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',item['id']):
            raise ValueError('Unsafe listing ID')
        item['view_path'] = f'docs/listings/{item["suite"]}--{item["id"]}.md'
    return records


def render(item):
    text = (f'# {item["title"]}\n\nGenerated view; the canonical source remains authoritative.\n\n'
            f'Listing ID: `{item["id"]}`. Chapter: {item["chapter"]}. Language: {item["language"]}.\n\n'
            f'Canonical source: [{item["source_path"]}](../../{item["source_path"]}).\n\n'
            f'Run from the repository root: `.venv/bin/python -B verify_all.py --chapter {item["chapter"]:02}`. '
            'The root command checks the lesson and its listing expectations in clean copies.\n\n'
            f'```{item["language"]}\n')
    start = text.count('\n') + 1
    text += item['code'] + ('' if item['code'].endswith('\n') else '\n') + '```\n'
    end = start + len(item['code'].splitlines()) - 1
    if item['expected_stdout'] is not None:
        stdout = item['expected_stdout']
        text += '\nExpected stdout:\n\n```text\n' + stdout + ('' if stdout.endswith('\n') else '\n') + '```\n'
    return text,start,end


def metadata(item):
    _,start,end = render(item)
    return {k:v for k,v in item.items() if k not in ('code','expected_stdout')} | {
        'canonical_code_sha256':sha256(item['code'].encode()).hexdigest(),
        'canonical_code_has_final_newline':item['code'].endswith('\n'),
        'view_code_start_line':start,'view_code_end_line':end,
        'repository_relative_link':item['view_path']}


def generate(root):
    items = canonical_listings(root)
    directory = root/'docs/listings'; directory.mkdir(exist_ok=True)
    for item in items:
        (root/item['view_path']).write_text(render(item)[0])
    (root/'docs/listings.json').write_text(json.dumps([metadata(i) for i in items],indent=2)+'\n')
    rows = [f'| {i["chapter"]} | `{i["id"]}` | [{i["title"]}]({i["view_path"].removeprefix("docs/")}) | [{i["source_path"]}](../{i["source_path"]}) |' for i in items]
    (root/'docs/LISTINGS.md').write_text('# All 72 canonical listings\n\nGenerated readable views preserve the canonical listing bodies exactly. Rendering never executes them. The root source check validates each view against its source and validates the machine-readable [listing map](listings.json), including source paths, code SHA-256 values and view line ranges.\n\n| Chapter | Listing ID | Readable view | Canonical source |\n|---|---|---|---|\n'+'\n'.join(rows)+'\n')


def check_views(root):
    items = canonical_listings(root)
    wanted = {item['view_path'] for item in items}
    actual = {str(p.relative_to(root)) for p in (root/'docs/listings').glob('*.md')}
    if actual != wanted:
        raise ValueError('Generated listing-view inventory differs')
    for item in items:
        if (root/item['view_path']).read_text() != render(item)[0]:
            raise ValueError(f'Generated view differs from canonical listing: {item["id"]}')
    if json.loads((root/'docs/listings.json').read_text()) != [metadata(i) for i in items]:
        raise ValueError('Machine-readable listing map differs from canonical sources')
    return len(items)


def render_refresher(item):
    return (f'# {item["title"]}\n\nGenerated readable view of the unchanged book refresher.\n\n'
            f'ID: `{item["id"]}`. Source: reader draft version {item["source_version"]}, '
            f'paragraph {item["source_paragraph"]}, {item["source_book_section"]}.\n\n'
            'Canonical source: [book_refresher_examples.json](book_refresher_examples.json). '
            'Run both examples from the repository root with '
            '`.venv/bin/python -B verify_all.py --prerequisites-only`.\n\n'
            f'```python\n{item["code"]}\n```\n\nExpected stdout:\n\n'
            f'```text\n{item["expected_stdout"]}```\n')


def check_readiness_views(root, write=False):
    items = json.loads((root/'prerequisites/book_refresher_examples.json').read_text())
    if [item['id'] for item in items] != ['refresher_python_values','refresher_sql_filtering']:
        raise ValueError('The two canonical book refresher IDs differ')
    for item in items:
        if sha256(item['code'].encode()).hexdigest() != item['code_sha256']:
            raise ValueError('Refresher code identity differs')
        target = root/item['view_path']
        expected = render_refresher(item)
        if write:
            target.write_text(expected)
        if target.read_text() != expected:
            raise ValueError(f'Book refresher view differs: {item["id"]}')
    return len(items)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true',help='regenerate views only, never expected lesson outputs')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if args.write:
        generate(root)
        if (root/'prerequisites/book_refresher_examples.json').exists():
            check_readiness_views(root,write=True)
    print(f'{check_views(root)} canonical listing views verified')
