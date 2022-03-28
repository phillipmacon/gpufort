# SPDX-License-Identifier: MIT
# Copyright (c) 2020-2022 Advanced Micro Devices, Inc. All rights reserved.
import os, sys
import re
import pyparsing as pyp

pyp.ParserElement.setDefaultWhitespaceChars("\r\n\t &;")

PYTHON_BINDING_FILE = "render.py.in"


class TemplateGenerator:

    def __init__(self,
                 template_dir,
                 macro_files,
                 macro_filters=["\w+"],
                 verbose=False):
        self.template_dir = template_dir
        self.macro_files = macro_files
        self.macro_filters = macro_filters
        self.verbose = verbose

    def iterate_macro_files(self, action):
        ident = pyp.pyparsing_common.identifier
        macro_open = pyp.Regex(r"\{%-?\s+macro").suppress()
        macro_close = pyp.Regex(r"\s-#\}").suppress()
        LPAR, RPAR = map(pyp.Suppress, "()")
        EQ = pyp.Suppress("=")
        printables = pyp.printables
        RHS = pyp.Regex(r"\[\]|\"[^\"]*\"|[0-9]+")
        arg = pyp.Group(ident + pyp.Optional(EQ + RHS, default=""))
        arglist = pyp.delimitedList(arg)
        macro = macro_open + ident + LPAR + arglist + RPAR

        for macrofile_name in self.macro_files:
            macrofile_ext = macrofile_name.split(".macros.")[-1]
            with open(os.path.join(self.template_dir, macrofile_name),
                      "r") as infile:
                content = infile.read()
                for parse_result in macro.searchString(content):
                    for regex in self.macro_filters:
                        if regex.match(parse_result[0]):
                            if self.verbose:
                                print(parse_result)
                            macro_name = parse_result[0]
                            macro_args = parse_result[1:]
                            macro_signature = "".join([macro_name,"(",\
                                                       ",".join([arg[0] for arg in macro_args]),")"])
                            template_content = \
                              "".join(["{% import \"",macrofile_name, "\" as macros %}\n",\
                                      "{{ macros.",macro_signature," }}"])
                            template_name = ".".join(
                                [parse_result[0], "template", macrofile_ext])
                            action(os.path.join(self.template_dir,template_name),\
                                   template_content,\
                                   macro_name,macro_args)

    def create_autogenerated_templates(self):
        python_funcs = []
        def create_autogenerated_templates_action_(template_path,template_content,\
                                                   macro_name,macro_args):
            with open(template_path, "w") as outfile:
                outfile.write(template_content)
            template_basename = os.path.basename(template_path)
            template_ext = template_basename.split(".template.")[-1]
            func_name = macro_name + "_" + template_ext.replace(".", "_")
            python_funcs.append((func_name, macro_args, template_basename))

        self.iterate_macro_files(create_autogenerated_templates_action_)

        with open(os.path.join(self.template_dir, PYTHON_BINDING_FILE),
                  "w") as outfile:
            rendered_funcs = []
            if len(python_funcs):
                rendered_funcs.append("# autogenerated file")
            for func in python_funcs:
                python_func_arg_list = []
                for arg in func[1]:
                    if len(arg[1]):
                        python_func_arg_list.append("=".join(arg))
                    else:
                        python_func_arg_list.append(arg[0])
                context = ",\n      ".join(
                    ["\"{0}\" : {0}".format(arg[0]) for arg in func[1]])
                #
                rendered_funcs.append("""def {0}_ctx(context):
    return generate_code("{3}",context)
    """.format(func[0], ",".join(python_func_arg_list), context, func[2]))
                #
                rendered_funcs.append("""def {0}({1}):
    context = {{
      {2}
      }}
    return {0}_ctx(context)
    """.format(func[0], ",".join(python_func_arg_list), context, func[2]))
            outfile.write("\n".join(rendered_funcs))

    def delete_autogenerated_templates(self):
        def delete_autogenerated_templates_action_(template_path,template_content,\
                                                   macro_name,macro_args):
            if os.path.exists(template_path):
                os.remove(template_path)

        self.iterate_macro_files(delete_autogenerated_templates_action_)

        with open(os.path.join(self.template_dir, PYTHON_BINDING_FILE),
                  "w") as outfile:
            outfile.write("")

    def convert_macros_to_templates(self):
        """coverts selected macros to templates"""
        self.delete_autogenerated_templates()
        self.create_autogenerated_templates()
