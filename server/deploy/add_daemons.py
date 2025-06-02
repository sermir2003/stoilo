#!/usr/bin/env python3
"""
Script to add userspace daemons from add_demons.xml to config.xml (BOINC project config).

Usage:
    ./add_daemons.py /absolute/path/to/config.xml /absolute/path/to/add_demons.xml

This script:
  - Parses the main config.xml file and the add_demons.xml file.
  - Adds all <daemon> entries from add_demons.xml into the <daemons> section of config.xml.
  - Preserves XML declaration and indents the output for readability.
"""
import sys
import os
import xml.etree.ElementTree as ET


def load_tree(path):
    try:
        tree = ET.parse(path)
        return tree
    except ET.ParseError as e:
        sys.stderr.write(f"Error parsing XML file '{path}': {e}\n")
        sys.exit(1)
    except FileNotFoundError:
        sys.stderr.write(f"File not found: '{path}'\n")
        sys.exit(1)


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: python add_daemons.py /path/to/config.xml /path/to/add_demons.xml\n")
        sys.exit(1)

    config_path, add_path = sys.argv[1], sys.argv[2]

    if not os.path.isabs(config_path) or not os.path.isabs(add_path):
        sys.stderr.write("Please provide absolute paths for both XML files.\n")
        sys.exit(1)

    config_tree = load_tree(config_path)
    add_tree = load_tree(add_path)

    config_root = config_tree.getroot()
    add_root = add_tree.getroot()

    daemons_elem = config_root.find('daemons')
    if daemons_elem is None:
        daemons_elem = ET.SubElement(config_root, 'daemons')

    added = 0
    for daemon in add_root.findall('daemon'):
        daemons_elem.append(daemon)
        added += 1

    if added == 0:
        print("No daemons found in add_demons.xml.")
    else:
        try:
            ET.indent(config_root, space="    ", level=0)
        except AttributeError:
            pass
        config_tree.write(config_path, encoding='utf-8', xml_declaration=True)
        print(f"Added {added} daemon(s) to '{config_path}'.")

if __name__ == '__main__':
    main()
