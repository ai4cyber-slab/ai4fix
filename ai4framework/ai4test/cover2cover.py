import sys
import xml.etree.ElementTree as ET
import re
import os.path
from pathlib import Path


def find_lines(j_package, filename):
    lines = []
    sourcefiles = j_package.findall("sourcefile")
    for sourcefile in sourcefiles:
        if sourcefile.attrib.get("name") == os.path.basename(filename):
            lines.extend(sourcefile.findall("line"))
    return lines


def line_is_after(jm, start_line):
    return int(jm.attrib.get('line', 0)) > start_line


def method_lines(jmethod, jmethods, jlines):
    start_line = int(jmethod.attrib.get('line', 0))
    larger = [int(jm.attrib.get('line', 0)) for jm in jmethods if line_is_after(jm, start_line)]
    end_line = min(larger) if larger else 99999999

    for jline in jlines:
        if start_line <= int(jline.attrib['nr']) < end_line:
            yield jline


def convert_lines(j_lines, into):
    c_lines = ET.SubElement(into, 'lines')
    for jline in j_lines:
        mb = int(jline.attrib['mb'])
        cb = int(jline.attrib['cb'])
        ci = int(jline.attrib['ci'])

        cline = ET.SubElement(c_lines, 'line')
        cline.set('number', jline.attrib['nr'])
        cline.set('hits', '1' if ci > 0 else '0')

        if mb + cb > 0:
            percentage = str(int(100 * (float(cb) / (float(cb) + float(mb))))) + '%'
            cline.set('branch', 'true')
            cline.set('condition-coverage', f"{percentage} ({cb}/{cb + mb})")
            cond = ET.SubElement(ET.SubElement(cline, 'conditions'), 'condition')
            cond.set('number', '0')
            cond.set('type', 'jump')
            cond.set('coverage', percentage)
        else:
            cline.set('branch', 'false')


def guess_filename(pkg_name, sourcefilename):
    return str(Path(pkg_name) / sourcefilename)


def add_counters(source, target):
    target.set('line-rate', counter(source, 'LINE'))
    target.set('branch-rate', counter(source, 'BRANCH'))
    target.set('complexity', counter(source, 'COMPLEXITY', sum_values))


def fraction(covered, missed):
    return covered / (covered + missed) if (covered + missed) > 0 else 0.0


def sum_values(covered, missed):
    return covered + missed


def counter(source, type, operation=fraction):
    cs = source.findall('counter')
    c = next((ct for ct in cs if ct.attrib.get('type') == type), None)
    if c is not None:
        covered = float(c.attrib['covered'])
        missed = float(c.attrib['missed'])
        return str(operation(covered, missed))
    return '0.0'


def convert_method(j_method, j_lines):
    c_method = ET.Element('method')
    c_method.set('name', j_method.attrib['name'])
    c_method.set('signature', j_method.attrib['desc'])
    add_counters(j_method, c_method)
    convert_lines(j_lines, c_method)
    return c_method


def convert_class(j_class, j_package, pkg_name):
    c_class = ET.Element('class')
    filename = j_class.attrib.get('sourcefilename')
    full_path = guess_filename(pkg_name, filename)

    c_class.set('name', j_class.attrib['name'].replace('/', '.'))
    c_class.set('filename', full_path)

    all_j_lines = list(find_lines(j_package, filename))
    c_methods = ET.SubElement(c_class, 'methods')
    all_j_methods = list(j_class.findall('method'))
    for j_method in all_j_methods:
        j_method_lines = method_lines(j_method, all_j_methods, all_j_lines)
        c_methods.append(convert_method(j_method, j_method_lines))
    add_counters(j_class, c_class)
    convert_lines(all_j_lines, c_class)
    return c_class


def convert_package(j_package):
    name = j_package.attrib['name']
    c_package = ET.Element('package')
    c_package.attrib['name'] = name.replace('/', '.')
    c_classes = ET.SubElement(c_package, 'classes')
    for j_class in j_package.findall('class'):
        c_classes.append(convert_class(j_class, j_package, name))
    add_counters(j_package, c_package)
    return c_package


def convert_root(source, target, source_roots):
    session = source.find('sessioninfo')
    if session is not None:
        target.set('timestamp', str(int(session.attrib['start']) / 1000))
    sources = ET.SubElement(target, 'sources')
    for s in source_roots:
        ET.SubElement(sources, 'source').text = s
    packages = ET.SubElement(target, 'packages')
    for package in source.findall('package'):
        packages.append(convert_package(package))
    add_counters(source, target)


def jacoco2cobertura(filename, source_roots=['.'], state="pre"):
    if filename == '-':
        root = ET.fromstring(sys.stdin.read())
    else:
        tree = ET.parse(filename)
        root = tree.getroot()

    into = ET.Element('coverage')
    convert_root(root, into, source_roots)

    output_filename = Path(filename).with_name(f'cobertura-{state}-report.xml')
    tree = ET.ElementTree(into)
    tree.write(output_filename, encoding="utf-8", xml_declaration=True)
    print(f"✅ Cobertura-style report generated: {output_filename}")
    return output_filename


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: cover2cover.py FILENAME [SOURCE_ROOTS]")
        sys.exit(1)

    filename = sys.argv[1]
    source_roots = sys.argv[2:] if len(sys.argv) > 2 else ['.']
    jacoco2cobertura(filename, source_roots)

