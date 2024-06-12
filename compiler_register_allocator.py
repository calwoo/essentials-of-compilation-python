import compiler
from graph import UndirectedAdjList
from typing import List, Tuple, Set, Dict
from ast import *
from x86_ast import *
from typing import Set, Dict, Tuple

from priority_queue import PriorityQueue

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
        graph = UndirectedAdjList()
        for i in p.body:
            match i:
                case Instr("movq", (src, dest)):
                    live_after_instr = live_after[i]
                    for v in live_after_instr:
                        if v != src and v != dest:
                            graph.add_edge(dest, v)
                case _:
                    write_locs = self.write_vars(i)
                    live_after_instr = live_after[i]
                    for d in write_locs:
                        for v in live_after_instr:
                            if v != d:
                                graph.add_edge(d, v)
        
        return graph

    ############################################################################
    # Allocate Registers
    ############################################################################

    # Returns the coloring and the set of spilled variables.
    def color_graph(
        self, graph: UndirectedAdjList, variables: Set[location]
    ) -> Tuple[Dict[location, int], Set[location]]:
        coloring = {}
        saturations = {v: set() for v in variables}
        num_variables = len(variables)
        while len(coloring) < num_variables:
            # select max saturated variable
            comparator = lambda x, y: len(x) < len(y)
            pqueue = PriorityQueue(comparator)
            for v in variables:
                if v not in coloring:
                    pqueue.push(v)
            max_saturated_v = pqueue.pop()

            # pick color
            color = 0
            while color in saturations[max_saturated_v]:
                color += 1
            coloring[max_saturated_v] = color

            # add color to saturation sets of neighbors in interference graph
            for nb in graph.adjacent(max_saturated_v):
                saturations[nb].add(color)

        return coloring, variables

    def allocate_registers(self, p: X86Program, graph: UndirectedAdjList) -> X86Program:
        variables = set(graph.vertices)
        coloring, _ = self.color_graph(graph, variables)

        # get assignments
        register_map = {
            0: Reg("rcx"), 1: Reg("rdx"), 2: Reg("rsi"), 3: Reg("rdi"),
            4: Reg("r8"), 5: Reg("r9"), 6: Reg("r10"), 7: Reg("rbx"),
            8: Reg("r12"), 9: Reg("r13"), 10: Reg("r14")
        }

        mapping = {}
        for loc, color in coloring.items():
            if color < 11:
                mapping[loc] = register_map[color]
            else:
                # spill to stack
                offset = -8 * (color - 11 + 1)
                stack_pos = Deref("rbp", offset)
                mapping[loc] = stack_pos

        # alter instructions
        new_instrs = []
        for i in p.body:
            match i:
                case Instr(opcode, args):
                    new_args = []
                    for a in args:
                        if isinstance(a, Variable):
                            reg = mapping[a]
                            new_args.append(reg)
                        else:
                            new_args.append(a)

                    new_i = Instr(opcode, tuple(new_args))
                    new_instrs.append(new_i)
                case _:
                    new_instrs.append(i)

        new_p = X86Program(body=new_instrs)
        return new_p

    ############################################################################
    # Assign Homes
    ############################################################################

    def assign_homes(self, pseudo_x86: X86Program) -> X86Program:
        live_afters = self.uncover_live(pseudo_x86)
        interference_graph = self.build_interference(pseudo_x86, live_afters)
        return self.allocate_registers(pseudo_x86, interference_graph)

    ###########################################################################
    # Patch Instructions
    ###########################################################################

    def patch_instr(self, i: instr) -> List[instr]:
        match i:
            case Instr(opcode, (Deref(reg1, offset1), Deref(reg2, offset2))):
                if reg1 == reg2 and offset1 == offset2:
                    return []
    
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

    ###########################################################################
    # Prelude & Conclusion
    ###########################################################################

    def prelude_and_conclusion(self, p: X86Program) -> X86Program:
        # YOUR CODE HERE
        pass
