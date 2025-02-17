#!/usr/bin/python3
# coding: utf-8 

# Converts a Godot Class XML file to an MD file
#
# There is nothing configurable in this file
# Run it without arguments for usage


import sys
import re
import xml.etree.ElementTree as ET
from time import gmtime, strftime
import os
import markdown
import bbcode_to_markdown


def make_text(text, module_class_names, current_class_name):
    return bbcode_to_markdown.format_text(text, module_class_names, current_class_name, '')


# `args` is a list of XML elements
def make_arglist(args, module_class_names):
    s = "("
    for arg_index, arg in enumerate(args):
        if arg_index > 0:
            s += ","
        s += " " + markdown.make_type(arg.attrib['type'], '', module_class_names) + " " + arg.attrib['name']
        if 'default' in arg.attrib:
            s += "=" + arg.attrib['default']
    s += " )"
    return s


# `items` is a list of XML elements
def make_constants(items, module_class_names, current_class_name):
    s = ""
    for item in items:
        s += "- "

        # In Godot docs, both constants and enum items can be referred using `[constant ClassName.ENUM_ITEM]` instead
        # of using the `enum` tag.
        s += make_custom_internal_anchor(item.attrib['name'])

        s += "**" + item.attrib['name'] + "** = **" + item.attrib['value'] + "**"
        text = item.text.strip()
        if text != "":
            s += " --- " + make_text(item.text, module_class_names, current_class_name)
        s += "\n"
    return s


def make_custom_internal_link(name):
    assert name.find(' ') == -1
    return markdown.make_link(name, "#i_" + name)


# This is a hack we can do because Markdown allows to fallback on HTML
def make_custom_internal_anchor(name):
    return '<span id="i_' + name + '"></span>'


class ClassDoc:
    def __init__(self, name):
        self.name = name
        self.parent_name = ""
        self.children = []
        self.is_module = False
        self.xml_tree = None
        self.xml_file_path = ""


# `xml_tree` is the XML tree obtained with `ET.parse(filepath)`
# `f_out` is the path to the destination file. Use '-' for to print to stdout.
# `module_class_names` is a list of strings. Each string is a class name.
# `derived_classes_map` is a dictionary where keys are class names, and values are list of derived class names.
def process_xml(klass, f_out, module_class_names):
    #print("Parsing", f_xml)

    xml_tree = klass.xml_tree

    root = xml_tree.getroot()
    if root.tag != "class":
        print("Error: No class found. Not a valid Godot class XML file!\n")
        sys.exit(1)

    current_class_name = root.attrib['name']

    # Header
    out = "# " + current_class_name + "\n\n"
    out += "Inherits: " + markdown.make_type(root.attrib['inherits'], '', module_class_names) + "\n\n"

    if len(klass.children) > 0:
        links = []
        for child in klass.children:
            links.append(markdown.make_type(child.name, '', module_class_names))
        out += "Inherited by: " + ', '.join(links) + "\n\n"

    if 'is_experimental' in root.attrib and root.attrib['is_experimental'] == 'true':
        out += ("!!! warning\n    This class is marked as experimental. "
            "It is subject to likely change or possible removal in future versions. Use at your own discretion.")
        out += "\n"

    out += make_text(root.find('brief_description').text, module_class_names, current_class_name) + "\n\n"

    text = make_text(root.find('description').text, module_class_names, current_class_name)
    if text.strip() != "":
        out += "## Description: \n\n" + text + "\n\n"

    # Tutorials
    tutorials = root.find('tutorials')
    if tutorials is not None:
        links = tutorials.findall('link')
        if len(links) > 0:
            out += "## Tutorials: \n\n"
            for link in links:
                out += "- [" + link.attrib['title'] + "](" + link.text + ")\n"

    # Properties summary
    members = []
    members_container = root.find('members')
    if members_container is not None:
        members = members_container.findall('member')
        if len(members) > 0:
            out += "## Properties: \n\n"
            table = [["Type", "Name", "Default"]]
            for member in members:
                row = [
                    "`" + member.attrib['type'] + "`",
                    make_custom_internal_link(member.attrib['name'])
                ]
                if 'default' in member.attrib:
                    row.append(member.attrib['default'])
                else:
                    row.append("")
                table.append(row)
            out += markdown.make_table(table)
            out += "\n\n"
        
    # Methods summary
    methods = []
    methods_container = root.find('methods')
    if methods_container is not None:
        methods = methods_container.findall('method')

        if len(methods) > 0:
            out += "## Methods: \n\n"
            table = [["Return", "Signature"]]

            # TODO Remove from list if it's a getter/setter of a property
            for method in methods:
                signature = make_custom_internal_link(method.attrib['name']) + " "
                args = method.findall('param')
                signature += make_arglist(args, module_class_names)
                signature += " "

                if 'qualifiers' in method.attrib:
                    signature += method.attrib['qualifiers']

                return_node = method.find('return')

                row = [
                    markdown.make_type(return_node.attrib['type'], '', module_class_names),
                    signature
                ]
                table.append(row)

            out += markdown.make_table(table)
            out += "\n\n"
    
    # Signals
    signals = []
    signals_container = root.find('signals')
    if signals_container is not None:
        signals = signals_container.findall('signal')

        if len(signals) > 0:
            out += "## Signals: \n\n"

            for signal in signals:
                out += "- "
                out += signal.attrib['name']

                args = signal.findall('param')
                out += make_arglist(args, module_class_names)
                out += " \n\n"

                desc = signal.find('description')
                if desc is not None:
                    text = make_text(desc.text, module_class_names, current_class_name)
                    if text != "":
                        out += text
                        out += "\n\n"
    
    # Enumerations and constants
    constants_container = root.find('constants')
    if constants_container is not None:
        generic_constants = constants_container.findall('constant')

        enums = {}
        constants = []

        for generic_constant in generic_constants:
            if 'enum' in generic_constant.attrib:
                name = generic_constant.attrib['enum']
                if name in enums:
                    enum_items = enums[name]
                else:
                    enum_items = []
                    enums[name] = enum_items
                enum_items.append(generic_constant)
            else:
                constants.append(generic_constant)
        
        # Enums
        if len(enums) > 0:
            out += "## Enumerations: \n\n"

            for enum_name, enum_items in enums.items():
                out += "enum **" + enum_name + "**: \n\n"
                out += make_constants(enum_items, module_class_names, current_class_name)
                out += "\n"
            
            out += "\n"

        # Constants
        if len(constants) > 0:
            out += "## Constants: \n\n"
            out += make_constants(constants, module_class_names, current_class_name)
            out += "\n"
    
    # Property descriptions
    if len(members) > 0:
        out += "## Property Descriptions\n\n"

        for member in members:
            out += "- " + markdown.make_type(member.attrib['type'], '', module_class_names) \
                + make_custom_internal_anchor(member.attrib['name']) + " **" + member.attrib['name'] + "**"
            if 'default' in member.attrib:
                out += " = " + member.attrib['default']
            out += "\n\n"

            if member.text is not None:
                text = make_text(member.text, module_class_names, current_class_name)
                if text.strip() != "":
                    out += text
                    out += "\n"

            out += "\n"
    
    # Method descriptions
    if len(methods) > 0:
        out += "## Method Descriptions\n\n"

        for method in methods:
            return_node = method.find('return')
            out += "- " + markdown.make_type(return_node.attrib['type'], '', module_class_names) \
                + make_custom_internal_anchor(method.attrib['name']) + " **" + method.attrib['name'] + "**"
            args = method.findall('param')
            out += make_arglist(args, module_class_names)
            out += " "
            if 'qualifiers' in method.attrib:
                signature += method.attrib['qualifiers']

            out += "\n\n"

            desc = method.find('description')
            if desc is not None:
                text = make_text(desc.text, module_class_names, current_class_name)
                if text.strip() != "":
                    out += text
                    out += "\n"
            
            out += "\n"

    # Footer
    out += "_Generated on " + strftime("%b %d, %Y", gmtime()) + "_\n" 
    #Full time stamp "%Y-%m-%d %H:%M:%S %z"

    if f_out == '-':
        print(out)
    else:
        outfile = open(f_out, mode='a', encoding='utf-8')
        outfile.write(out)


# Generates a Markdown file containing a list of all the classes, organized in a hierarchy
def generate_classes_index(output_path, classes_by_name, verbose, module_class_names):
    root_classes = []
    for class_name, klass in classes_by_name.items():
        if klass.parent_name == "":
            root_classes.append(klass)

    lines = ["# All classes", ""]
    indent = "    "

    def do_branch(lines, classes, level, indent, module_class_names):
        for klass in classes:
            # TODO Format for abstract classes? XML files don't contain that information...
            link = klass.name
            if klass.is_module:
                link = markdown.make_type(klass.name, '', module_class_names)
            lines.append(level * indent + "- " + link)
            
            if len(klass.children) > 0:
                do_branch(lines, klass.children, level + 1, indent, module_class_names)

    for klass in root_classes:
        lines.append("- " + klass.name)
        do_branch(lines, klass.children, 1, indent, module_class_names)
    
    out = "\n".join(lines)

    if verbose:
        print("Writing", output_path)

    with open(output_path, mode='w', encoding='utf-8') as f:
        f.write(out)


def process_xml_folder(src_dir, dst_dir, verbose):
    # Make output dir and remove old files
    if not os.path.isdir(dst_dir):
        if verbose:
            print("Making output directory: " + dst_dir)
        os.makedirs(dst_dir)

    for i in dst_dir.glob("*.md"):
        if verbose:
            print("Removing old: ", i)
        os.remove(i)

    # Convert files to MD
    xml_files = list(src_dir.glob("*.xml"))
    doc_files = []
    count = 0

    module_class_names = []
    for xml_file in xml_files:
        module_class_names.append(xml_file.stem)
    
    # Parse all XML files
    class_xml_trees = {}
    for src_filepath in xml_files:
        xml_tree = ET.parse(src_filepath)

        root = xml_tree.getroot()
        if root.tag != "class":
            print("Error: No class found in ", src_filepath, "!\n")
            continue

        class_xml_trees[src_filepath] = xml_tree

    # Build class objects
    classes_by_name = {}

    for filename, xml_tree in class_xml_trees.items():
        root = xml_tree.getroot()

        klass = ClassDoc(root.attrib['name'])
        klass.xml_tree = xml_tree
        klass.xml_file_path = filename
        klass.parent_name = root.attrib['inherits']
        klass.is_module = True

        classes_by_name[klass.name] = klass
            
    # Complete hierarchy with Godot base classes
    # TODO It would be nice to load this from Godot's own XML files?
    godot_classes = [
        ["Object", ""],
        ["Node", "Object"],
        ["RefCounted", "Object"],
        ["Resource", "RefCounted"],
        ["Node3D", "Node"],
        ["RigidBody3D", "Node3D"]
    ]
    for gdclass in godot_classes:
        klass = ClassDoc(gdclass[0])
        klass.parent_name = gdclass[1]
        klass.is_module = False
        classes_by_name[klass.name] = klass

    # Populate children
    for class_name, klass in classes_by_name.items():
        if klass.parent_name != "":
            if klass.parent_name in classes_by_name:
                parent = classes_by_name[klass.parent_name]
                parent.children.append(klass)

    # Sort
    for class_name, klass in classes_by_name.items():
        klass.children.sort(key = lambda x: x.name)

    # Generate Markdown files
    for class_name, klass in classes_by_name.items():
        if klass.is_module:
            dest = dst_dir / (klass.xml_file_path.stem + ".md")
            if verbose:
                print("Converting ", klass.xml_file_path, dest)
            process_xml(klass, dest, module_class_names)
            count += 1
            doc_files.append(dest)

    generate_classes_index(dst_dir / "all_classes.md", classes_by_name, verbose, module_class_names)
    #count += 1

    print("Generated %d files in %s." % (count, dst_dir))


###########################
## Main()

# If called from command line
if __name__ == "__main__":
    # Print usage if no args
    if len(sys.argv) < 2:
        print("Usage: %s infile [outfile]" % sys.argv[0])
        print("Prints to stdout if outfile is not specified.\n")
        sys.exit(0)

    # Input file
    infile = sys.argv[1]

    # Print to screen if no output
    if len(sys.argv) < 3:
        outfile = "-"
    else: 
        outfile = sys.argv[2]

    xml_tree = ET.parse(infile)
    process_xml(xml_tree, outfile, [], {})

