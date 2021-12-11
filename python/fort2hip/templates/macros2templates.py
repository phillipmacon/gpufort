#!/usr/bin/env python3
import os,sys
import re
import pyparsing as pyp

PARENT_DIR = os.path.abspath(os.path.join(__file__,".."))

MACRO_FILES = [
  "hip_implementation.macros.hip.cpp"
]
MACRO_FILTERS = [
  re.compile(r"render_(gpu|cpu)_kernel(_launcher)?\b")
]

pyp.ParserElement.setDefaultWhitespaceChars("\r\n\t &;")

def iterate_macro_files(action):
    ident       = pyp.pyparsing_common.identifier
    macro_open  = pyp.Regex(r"\{%-?\s+macro").suppress()
    macro_close = pyp.Regex(r"\s-#\}").suppress()
    LPAR,RPAR   = map(pyp.Suppress,"()")
    EQ          = pyp.Suppress("=")
    RHS         = pyp.Regex(r"\[\]|\"\w*\"|[0-9]+").suppress()
    arg1        = ident 
    arg2        = ident + EQ + RHS 
    arglist     = pyp.delimitedList(arg2 | arg1)
    macro       = macro_open + ident + LPAR + arglist + RPAR 

    for macrofile_name in MACRO_FILES:
        macrofile_ext = macrofile_name.split(".macros.")[-1]
        with open(os.path.join(PARENT_DIR,macrofile_name), "r") as infile:
            content = infile.read()
            for parse_result in macro.searchString(content):
                for regex in MACRO_FILTERS:
                    if regex.match(parse_result[0]):
                       macro_name = parse_result[0]
                       macro_args = parse_result[1:]
                       macro_signature = "".join([macro_name,"(",\
                                                  ",".join(macro_args),")"])
                       template_content = \
                         "".join(["{{ import ",macrofile_name, " as macros }}\n",\
                                 "{{ macros.",macro_signature," }}"])
                       template_name = ".".join([parse_result[0],"template",macrofile_ext])
                       action(template_name,\
                              template_content,\
                              macro_name,macro_args)

def create_templates():
    python_callers = []
    def create_templates_action_(template_name,template_content,\
                                 macro_name,macro_args):
        with open(os.path.join(PARENT_DIR,template_name),"w") as outfile:
            outfile.write(template_content)
        python_callers.append((macro_name,macro_args,template_name))
    iterate_macro_files(create_templates_action_)
    
    with open(os.path.join(PARENT_DIR,"model.py.in"),"w") as outfile: 
        rendered_callers = []
        if len(python_callers):
            rendered_callers.append("# autogenerated file")
        for caller in python_callers:
            context = ",\n    ".join(["\"{0}\":{0}".format(arg) for arg in caller[1]])
            rendered_callers.append("""def {0}({1}):
  context = {{
    {2} 
  }}
  return BaseModel.__init__(self,"{3}").generate_code(context)
""".format(caller[0],",".join(caller[1]),context,caller[2]))
        outfile.write("\n".join(rendered_callers))

def delete_templates():
    def delete_templates_action_(template_path,template_content,\
                                 macro_name,macro_args):
        if os.path.exists(template_path):
            os.remove(template_path)
    iterate_macro_files(delete_templates_action_)
    with open(os.path.join(PARENT_DIR,"model.py.in"),"w") as outfile:
        outfile.write("")

delete_templates()    
create_templates()