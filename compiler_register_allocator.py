import compiler
from graph import UndirectedAdjList
from typing import List, Tuple, Set, Dict
from ast import *
from x86_ast import *
from typing import Set, Dict, Tuple

# Skeleton code for the chapter on Register Allocation


class Compiler(compiler.Compiler):

    ###########################################################################
    # Uncover Live
    ###########################################################################

    def read_vars(self, i: instr) -> Set[location]:
        match i:
            case Instr(opcode, args):
                if opcode in ["addq", "subq", "movq", "negq"]:
                    rvars = set()
                    for a in args:
                        if isinstance(a, Variable) or isinstance(a, Reg):
                            rvars.add(a)
                    return rvars
                else:
                    return set()
            case Callq(f, arity):
                arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
                return set([
                    Reg(r) for r in arg_regs[:arity]
                ])
            case _:
                return set()

    def write_vars(self, i: instr) -> Set[location]:
        match i:
            case Instr(opcode, args):
                if opcode in ["addq", "subq", "movq", "negq"]:
                    return set([args[-1]])
                else:
                    return set()
            case Callq(f, arity):
                # return caller-saved registers
                caller_saved_regs = ["rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"]
                return set([
                    Reg(r) for r in caller_saved_regs
                ])
            case _:
                return set()

    def uncover_live(self, p: X86Program) -> Dict[instr, Set[location]]:
        lives = []
        for i in reversed(p.body):
            if len(lives) == 0:
                lives.append((i, set()))
            else:
                _, prev_live = lives[-1]
                rvars = self.read_vars(i)
                wvars = self.write_vars(i)
                live = prev_live.difference(wvars).union(rvars)
                lives.append((i, live))
        return {i: lv for (i, lv) in lives}

    ############################################################################
    # Build Interference
    ############################################################################

    def build_interference(
        self, p: X86Program, live_after: Dict[instr, Set[location]]
    ) -> UndirectedAdjList:
        # YOUR CODE HERE
        pass

    ############################################################################
    # Allocate Registers
    ############################################################################

    # Returns the coloring and the set of spilled variables.
    def color_graph(
        self, graph: UndirectedAdjList, variables: Set[location]
    ) -> Tuple[Dict[location, int], Set[location]]:
        # YOUR CODE HERE
        pass

    def allocate_registers(self, p: X86Program, graph: UndirectedAdjList) -> X86Program:
        # YOUR CODE HERE
        pass

    ############################################################################
    # Assign Homes
    ############################################################################

    def assign_homes(self, pseudo_x86: X86Program) -> X86Program:
        # YOUR CODE HERE
        pass

    ###########################################################################
    # Patch Instructions
    ###########################################################################

    def patch_instructions(self, p: X86Program) -> X86Program:
        # YOUR CODE HERE
        pass

    ###########################################################################
    # Prelude & Conclusion
    ###########################################################################

    def prelude_and_conclusion(self, p: X86Program) -> X86Program:
        # YOUR CODE HERE
        pass
