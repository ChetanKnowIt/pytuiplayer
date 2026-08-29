import ast
from pathlib import Path

'''
Generate a .pyi stub file from a Python source file using the ast module.
This script reads a Python source file, parses it into an AST, and then generates a stub file
containing class and function definitions with type annotations and ellipses for bodies.

Usage:
    python ast_stub.py <file.py>
    
The generated stub file will be saved as <file>_ast.pyi in the same directory.
'''

def unparse(node):
    return ast.unparse(node) if node else ""

class Skeleton(ast.NodeVisitor):
    def __init__(self):
        self.lines = []
        self.indent = 0

    def emit(self, line=""):
        self.lines.append("    " * self.indent + line)

    def visit_Module(self, node):
        for item in node.body:
            if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(item)

    def visit_ClassDef(self, node):
        bases = [unparse(b) for b in node.bases]
        base_str = f"({', '.join(bases)})" if bases else ""
        self.emit(f"class {node.name}{base_str}:")
        self.indent += 1

        has_members = False
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_members = True
                self.visit(item)

        if not has_members:
            self.emit("...")

        self.indent -= 1
        self.emit()

    def visit_FunctionDef(self, node):
        self._emit_function(node, async_=False)

    def visit_AsyncFunctionDef(self, node):
        self._emit_function(node, async_=True)

    def _emit_function(self, node, async_):
        args = []

        for a in node.args.posonlyargs:
            args.append(self.format_arg(a))
        if node.args.posonlyargs:
            args.append("/")

        for a in node.args.args:
            args.append(self.format_arg(a))

        if node.args.vararg:
            args.append("*" + self.format_arg(node.args.vararg))

        for a in node.args.kwonlyargs:
            args.append(self.format_arg(a))

        if node.args.kwarg:
            args.append("**" + self.format_arg(node.args.kwarg))

        defaults = [unparse(d) for d in node.args.defaults]
        for i, default in enumerate(defaults, start=len(args) - len(defaults)):
            args[i] += f" = {default}"

        ret = f" -> {unparse(node.returns)}" if node.returns else ""
        prefix = "async def" if async_ else "def"
        self.emit(f"{prefix} {node.name}({', '.join(args)}){ret}: ...")

    def format_arg(self, arg):
        if arg.annotation:
            return f"{arg.arg}: {unparse(arg.annotation)}"
        return arg.arg


def generate_stub(source_path: Path):
    target_path = source_path.with_name(source_path.stem + "_ast.pyi")

    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    skel = Skeleton()
    skel.visit(tree)

    target_path.write_text("\n".join(skel.lines), encoding="utf-8")
    print(f"✔ Stub written to: {target_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python ast_stub.py <file.py>")
        sys.exit(1)

    generate_stub(Path(sys.argv[1]))
