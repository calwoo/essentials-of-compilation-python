	.globl main
main:
    pushq %rbp
    movq %rsp, %rbp
    subq $16, %rsp
    movq $40, %rax
    addq $2, %rax
    movq %rax, -8(%rbp)
    movq -8(%rbp), %rdi
    callq print_int
    addq $16, %rsp
    popq %rbp
    retq 

