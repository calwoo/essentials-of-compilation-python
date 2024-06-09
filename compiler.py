import ast
from ast import *
from utils import *
from x86_ast import *
import os
from typing import List, Tuple, Set, Dict

Binding = Tuple[Name, expr]
Temporaries = List[Binding]


class Compiler:

    ############################################################################
    # Remove Complex Operands
    ############################################################################

    def rco_exp(self, e: expr, need_atomic: bool) -> Tuple[expr, Temporaries]:
        match e:
            case Constant(n):
                return Constant(n), []
            case Call(Name("input_int"), []):
                if need_atomic:
                    tmp = Name(generate_name("tmp"))
                    return tmp, [(tmp, Call(Name("input_int"), []))]
                else:
                    return Call(Name("input_int"), []), []
            case UnaryOp(USub(), exp):
                (atm, temps) = self.rco_exp(exp, True)
                usub = UnaryOp(USub(), atm)
                if need_atomic:
                    tmp = Name(generate_name("tmp"))
                    return tmp, temps + [(tmp, usub)]
                else:
                    return usub, temps
            case BinOp(exp1, Add(), exp2):
                (atm1, temps1) = self.rco_exp(exp1, True)
                (atm2, temps2) = self.rco_exp(exp2, True)
                add = BinOp(atm1, Add(), atm2)
                if need_atomic:
                    tmp = Name(generate_name("tmp"))
                    return tmp, temps1 + temps2 + [(tmp, add)]
                else:
                    return add, temps1 + temps2
            case BinOp(exp1, Sub(), exp2):
                (atm1, temps1) = self.rco_exp(exp1, True)
                (atm2, temps2) = self.rco_exp(exp2, True)
                sub = BinOp(atm1, Sub(), atm2)
                if need_atomic:
                    tmp = Name(generate_name("tmp"))
                    return tmp, temps1 + temps2 + [(tmp, sub)]
                else:
                    return sub, temps1 + temps2
            case Name(var):
                return Name(var), []
            case _:
                raise Exception("rco_exp unexpected " + repr(e))

    def rco_stmt(self, s: stmt) -> List[stmt]:
        match s:
            case Expr(Call(Name("print"), [exp])):
                (atm, temps) = self.rco_exp(exp, True)
                return [Assign([var], init) for (var, init) in temps] + [
                    Expr(Call(Name("print"), [atm]))
                ]
            case Expr(exp):
                (atm, temps) = self.rco_exp(exp, False)
                return [Assign([var], init) for (var, init) in temps]
            case Assign([Name(var)], exp):
                (atm, temps) = self.rco_exp(exp, False)
                return [Assign([x], init) for (x, init) in temps] + [
                    Assign([Name(var)], atm)
                ]
            case _:
                raise Exception("rco_stmt not implemented")

    def remove_complex_operands(self, p: Module) -> Module:
        match p:
            case Module(ss):
                sss = [self.rco_stmt(s) for s in ss]
                return Module(sum(sss, []))
        raise Exception("remove_complex_operands not implemented")

    ############################################################################
    # Select Instructions
    ############################################################################

    def select_arg(self, e: expr) -> arg:
        match e:
            case Constant(n):
                return Immediate(n)
            case Name(var):
                return Variable(var)

    def select_stmt(self, s: stmt) -> List[instr]:
        match s:
            case Expr(Call(Name("print"), [atm])):
                arg = self.select_arg(atm)
                return [
                    Instr("movq", (arg, Reg("rdi"))),
                    Callq(label_name("print_int"), 1)
                ]
            case Assign([Name(var)], exp):
                arg = self.select_arg(Name(var))
                match exp:
                    case Call(Name("input_int"), []):
                        return [
                            Callq(label_name("read_int"), 0),
                            Instr("movq", (Reg("rax"), arg)),
                        ]
                    case UnaryOp(USub(), atm):
                        arg0 = self.select_arg(atm)
                        return [
                            Instr("movq", (arg0, Reg("rax"))),
                            Instr("negq", (Reg("rax"),)),
                            Instr("movq", (Reg("rax"), arg)),
                        ]
                    case BinOp(atm1, Add(), atm2):
                        arg1 = self.select_arg(atm1)
                        arg2 = self.select_arg(atm2)
                        return [
                            Instr("movq", (arg1, Reg("rax"))),
                            Instr("addq", (arg2, Reg("rax"))),
                            Instr("movq", (Reg("rax"), arg)),
                        ]
                    case BinOp(atm1, Sub(), atm2):
                        arg1 = self.select_arg(atm1)
                        arg2 = self.select_arg(atm2)
                        return [
                            Instr("movq", (arg1, Reg("rax"))),
                            Instr("subq", (arg2, Reg("rax"))),
                            Instr("movq", (Reg("rax"), arg)),
                        ]
            case _:
                raise Exception("select_stmt not implemented")

    def select_instructions(self, p: Module) -> X86Program:
        instrs = []
        for s in p.body:
            x86_instrs = self.select_stmt(s)
            instrs.extend(x86_instrs)
        prog = X86Program(body=instrs)
        return prog

    ############################################################################
    # Assign Homes
    ############################################################################

    def assign_homes_arg(self, a: arg, home: Dict[Variable, arg]) -> arg:
        match a:
            case Variable(id_):
                if a in home:
                    return home[a]
                else:
                    n_existing_vars = len(home)
                    offset = -8 * (n_existing_vars + 1)
                    stack_arg = Deref("rbp", offset)
                    home[a] = stack_arg
                    return stack_arg
            case _:
                return a

    def assign_homes_instr(self, i: instr, home: Dict[Variable, arg]) -> instr:
        match i:
            case Instr(opcode, args):
                stack_args = []
                for a in args:
                    new_a = self.assign_homes_arg(a, home)
                    stack_args.append(new_a)
                return Instr(opcode, tuple(stack_args))
            case _:
                # other instructions don't involve variables or registers,
                # so just purely pass
                return i

    def assign_homes(self, p: X86Program) -> X86Program:
        new_instrs = []
        stack_homes = {}
        for i in p.body:
            new_i = self.assign_homes_instr(i, stack_homes)
            new_instrs.append(new_i)
        new_p = X86Program(body=new_instrs)
        return new_p

    ############################################################################
    # Patch Instructions
    ############################################################################

    def patch_instr(self, i: instr) -> List[instr]:
        match i:
            case Instr(opcode, (Deref(reg1, offset1), Deref(reg2, offset2))):
                return [
                    Instr("movq", (Deref(reg1, offset1), Reg("rax"))),
                    Instr(opcode, (Reg("rax"), Deref(reg2, offset2))),
                ]
            case _:
                return [i]

    def patch_instructions(self, p: X86Program) -> X86Program:
        new_instrs = []
        for i in p.body:
            new_is = self.patch_instr(i)
            new_instrs.extend(new_is)
        new_p = X86Program(body=new_instrs)
        return new_p

    ############################################################################
    # Prelude & Conclusion
    ############################################################################

    def prelude_and_conclusion(self, p: X86Program) -> X86Program:
        # compute how many variables are in program
        max_offset = 0
        for i in p.body:
            match i:
                case Instr(opcode, (Deref(reg, offset), arg)):
                    max_offset = max(max_offset, -offset)
                case Instr(opcode, (arg, Deref(reg, offset))):
                    max_offset = max(max_offset, -offset)
                case _:
                    continue

        # x86-64 requires stack pointer to be 16-byte aligned in prelude
        if max_offset % 16 != 0:
            max_offset += (16 - max_offset % 16)

        prelude = [
            Instr("pushq", (Reg("rbp"),)),
            Instr("movq", (Reg("rsp"), Reg("rbp"))),
            Instr("subq", (Immediate(max_offset), Reg("rsp"))),
        ]

        conclusion = [
            Instr("addq", (Immediate(max_offset), Reg("rsp"))),
            Instr("popq", (Reg("rbp"),)),
            Instr("retq", []),
        ]

        new_body = prelude + p.body + conclusion
        new_p = X86Program(body=new_body)
        return new_p
