	.intel_syntax noprefix
	.file	"copy_loops.cpp"
	.text
	.globl	_Z12copy_copylibRKN7copylib9copy_specE # -- Begin function _Z12copy_copylibRKN7copylib9copy_specE
	.p2align	4
	.type	_Z12copy_copylibRKN7copylib9copy_specE,@function
_Z12copy_copylibRKN7copylib9copy_specE: # @_Z12copy_copylibRKN7copylib9copy_specE
# %bb.0:
	push	rbp
	push	r15
	push	r14
	push	r13
	push	r12
	push	rbx
	sub	rsp, 88
	mov	rax, qword ptr [rdi + 88]
	sub	rax, qword ptr [rdi + 80]
	mov	qword ptr [rsp + 24], rax       # 8-byte Spill
	jle	.LBB0_33
# %bb.1:
	mov	rbx, rdi
	mov	r15, qword ptr [rdi + 56]
	sub	r15, qword ptr [rdi + 32]
	mov	r14, qword ptr [rdi + 152]
	sub	r14, qword ptr [rdi + 128]
	xor	r8d, r8d
	xor	edx, edx
	xor	ecx, ecx
	xor	ebp, ebp
	mov	qword ptr [rsp + 32], r15       # 8-byte Spill
	jmp	.LBB0_2
	.p2align	4
.LBB0_27:                               #   in Loop: Header=BB0_2 Depth=1
	xor	ecx, ecx
	mov	rdx, qword ptr [rsp + 16]       # 8-byte Reload
	mov	r8, qword ptr [rsp + 8]         # 8-byte Reload
.LBB0_31:                               #   in Loop: Header=BB0_2 Depth=1
	test	rcx, rcx
	cmove	rdx, r13
	cmove	r8, r12
	add	rcx, r15
	add	rbp, r15
	cmp	rbp, qword ptr [rsp + 24]       # 8-byte Folded Reload
	mov	r15, qword ptr [rsp + 32]       # 8-byte Reload
	jge	.LBB0_32
.LBB0_2:                                # =>This Inner Loop Header: Depth=1
	mov	qword ptr [rsp + 8], r8         # 8-byte Spill
	mov	qword ptr [rsp + 16], rdx       # 8-byte Spill
	mov	rdi, qword ptr [rbx + 80]
	add	rdi, rbp
	mov	rsi, qword ptr [rbx + 56]
	mov	rax, qword ptr [rbx + 32]
	mov	r9, qword ptr [rbx + 40]
	mov	qword ptr [rsp + 80], rax       # 8-byte Spill
	sub	rsi, rax
	mov	r8, qword ptr [rbx + 64]
	mov	rax, rdi
	or	rax, rsi
	shr	rax, 32
	je	.LBB0_3
# %bb.4:                                #   in Loop: Header=BB0_2 Depth=1
	mov	rax, rdi
	cqo
	idiv	rsi
	jmp	.LBB0_5
	.p2align	4
.LBB0_3:                                #   in Loop: Header=BB0_2 Depth=1
	mov	eax, edi
	xor	edx, edx
	div	esi
                                        # kill: def $edx killed $edx def $rdx
.LBB0_5:                                #   in Loop: Header=BB0_2 Depth=1
	mov	qword ptr [rsp + 72], rdx       # 8-byte Spill
	sub	r8, r9
	imul	r8, rsi
	mov	rax, rdi
	or	rax, r8
	shr	rax, 32
	je	.LBB0_6
# %bb.7:                                #   in Loop: Header=BB0_2 Depth=1
	mov	rax, rdi
	cqo
	idiv	r8
	mov	r8, rax
	mov	rax, rdx
	or	rax, rsi
	shr	rax, 32
	je	.LBB0_9
.LBB0_10:                               #   in Loop: Header=BB0_2 Depth=1
	mov	rax, rdx
	cqo
	idiv	rsi
	mov	r12, rax
	jmp	.LBB0_11
	.p2align	4
.LBB0_6:                                #   in Loop: Header=BB0_2 Depth=1
	mov	eax, edi
	xor	edx, edx
	div	r8d
                                        # kill: def $edx killed $edx def $rdx
	mov	r8d, eax
	mov	rax, rdx
	or	rax, rsi
	shr	rax, 32
	jne	.LBB0_10
.LBB0_9:                                #   in Loop: Header=BB0_2 Depth=1
	mov	eax, edx
	xor	edx, edx
	div	esi
	mov	r12d, eax
.LBB0_11:                               #   in Loop: Header=BB0_2 Depth=1
	mov	qword ptr [rsp + 64], r9        # 8-byte Spill
	add	r8, qword ptr [rbx + 48]
	imul	r8, qword ptr [rbx + 24]
	mov	rax, qword ptr [rbx + 16]
	mov	qword ptr [rsp + 56], rax       # 8-byte Spill
	mov	rax, qword ptr [rbx + 128]
	mov	r10, qword ptr [rbx + 176]
	add	r10, rbp
	mov	r13, qword ptr [rbx + 152]
	mov	qword ptr [rsp + 48], rax       # 8-byte Spill
	sub	r13, rax
	mov	rsi, qword ptr [rbx + 160]
	mov	r11, qword ptr [rbx + 136]
	mov	rax, r10
	or	rax, r13
	shr	rax, 32
	je	.LBB0_12
# %bb.13:                               #   in Loop: Header=BB0_2 Depth=1
	mov	rax, r10
	cqo
	idiv	r13
	mov	r9, rdx
	jmp	.LBB0_14
	.p2align	4
.LBB0_12:                               #   in Loop: Header=BB0_2 Depth=1
	mov	eax, r10d
	xor	edx, edx
	div	r13d
	mov	r9d, edx
.LBB0_14:                               #   in Loop: Header=BB0_2 Depth=1
	mov	qword ptr [rsp + 40], r11       # 8-byte Spill
	sub	rsi, r11
	imul	rsi, r13
	mov	rax, r10
	or	rax, rsi
	shr	rax, 32
	je	.LBB0_15
# %bb.16:                               #   in Loop: Header=BB0_2 Depth=1
	mov	rax, r10
	cqo
	idiv	rsi
	mov	r11, rax
	mov	rax, rdx
	or	rax, r13
	shr	rax, 32
	je	.LBB0_18
.LBB0_19:                               #   in Loop: Header=BB0_2 Depth=1
	mov	rax, rdx
	cqo
	idiv	r13
	mov	r13, rax
	jmp	.LBB0_20
	.p2align	4
.LBB0_15:                               #   in Loop: Header=BB0_2 Depth=1
	mov	eax, r10d
	xor	edx, edx
	div	esi
                                        # kill: def $edx killed $edx def $rdx
	mov	r11d, eax
	mov	rax, rdx
	or	rax, r13
	shr	rax, 32
	jne	.LBB0_19
.LBB0_18:                               #   in Loop: Header=BB0_2 Depth=1
	mov	eax, edx
	xor	edx, edx
	div	r13d
	mov	r13d, eax
.LBB0_20:                               #   in Loop: Header=BB0_2 Depth=1
	add	r11, qword ptr [rbx + 144]
	imul	r11, qword ptr [rbx + 120]
	mov	rsi, qword ptr [rbx + 112]
	mov	rax, rdi
	or	rax, r15
	shr	rax, 32
	je	.LBB0_21
# %bb.22:                               #   in Loop: Header=BB0_2 Depth=1
	mov	rax, rdi
	cqo
	idiv	r15
	mov	rdi, rdx
	mov	rax, r10
	or	rax, r14
	shr	rax, 32
	je	.LBB0_24
.LBB0_25:                               #   in Loop: Header=BB0_2 Depth=1
	mov	rax, r10
	cqo
	idiv	r14
	jmp	.LBB0_26
	.p2align	4
.LBB0_21:                               #   in Loop: Header=BB0_2 Depth=1
	mov	eax, edi
	xor	edx, edx
	div	r15d
	mov	edi, edx
	mov	rax, r10
	or	rax, r14
	shr	rax, 32
	jne	.LBB0_25
.LBB0_24:                               #   in Loop: Header=BB0_2 Depth=1
	mov	eax, r10d
	xor	edx, edx
	div	r14d
                                        # kill: def $edx killed $edx def $rdx
.LBB0_26:                               #   in Loop: Header=BB0_2 Depth=1
	add	r12, qword ptr [rsp + 64]       # 8-byte Folded Reload
	add	r12, r8
	mov	r8, qword ptr [rsp + 72]        # 8-byte Reload
	add	r8, qword ptr [rsp + 80]        # 8-byte Folded Reload
	add	r13, qword ptr [rsp + 40]       # 8-byte Folded Reload
	add	r13, r11
	add	r9, qword ptr [rsp + 48]        # 8-byte Folded Reload
	mov	rax, r15
	sub	rax, rdi
	mov	r15, r14
	sub	r15, rdx
	mov	rdx, qword ptr [rsp + 24]       # 8-byte Reload
	sub	rdx, rbp
	cmp	r15, rax
	cmovge	r15, rax
	imul	r12, qword ptr [rsp + 56]       # 8-byte Folded Reload
	add	r12, r8
	imul	r13, rsi
	add	r13, r9
	cmp	rdx, r15
	cmovl	r15, rdx
	test	rcx, rcx
	je	.LBB0_27
# %bb.28:                               #   in Loop: Header=BB0_2 Depth=1
	mov	r8, qword ptr [rsp + 8]         # 8-byte Reload
	lea	rax, [rcx + r8]
	cmp	r12, rax
	mov	rdx, qword ptr [rsp + 16]       # 8-byte Reload
	jne	.LBB0_30
# %bb.29:                               #   in Loop: Header=BB0_2 Depth=1
	lea	rax, [rcx + rdx]
	cmp	r13, rax
	je	.LBB0_31
.LBB0_30:                               #   in Loop: Header=BB0_2 Depth=1
	mov	rdi, qword ptr [rbx + 104]
	add	rdi, rdx
	mov	rsi, qword ptr [rbx + 8]
	add	rsi, r8
	mov	rdx, rcx
	call	memcpy@PLT
	mov	r8, qword ptr [rsp + 8]         # 8-byte Reload
	mov	rdx, qword ptr [rsp + 16]       # 8-byte Reload
	xor	ecx, ecx
	jmp	.LBB0_31
.LBB0_32:
	test	rcx, rcx
	je	.LBB0_33
# %bb.34:
	add	rdx, qword ptr [rbx + 104]
	add	r8, qword ptr [rbx + 8]
	mov	rdi, rdx
	mov	rsi, r8
	mov	rdx, rcx
	add	rsp, 88
	pop	rbx
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	pop	rbp
	jmp	memcpy@PLT                      # TAILCALL
.LBB0_33:
	add	rsp, 88
	pop	rbx
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	pop	rbp
	ret
.Lfunc_end0:
	.size	_Z12copy_copylibRKN7copylib9copy_specE, .Lfunc_end0-_Z12copy_copylibRKN7copylib9copy_specE
                                        # -- End function
	.globl	_Z12rows_runtimePSt4bytelPKS_lll # -- Begin function _Z12rows_runtimePSt4bytelPKS_lll
	.p2align	4
	.type	_Z12rows_runtimePSt4bytelPKS_lll,@function
_Z12rows_runtimePSt4bytelPKS_lll:       # @_Z12rows_runtimePSt4bytelPKS_lll
# %bb.0:
	push	rbp
	push	r15
	push	r14
	push	r13
	push	r12
	push	rbx
	sub	rsp, 56
	test	r8, r8
	jle	.LBB1_4
# %bb.1:
	mov	rbx, r9
	cmp	r8, 1
	mov	qword ptr [rsp + 24], rdx       # 8-byte Spill
	mov	qword ptr [rsp + 16], rdi       # 8-byte Spill
	mov	qword ptr [rsp + 8], r8         # 8-byte Spill
	jne	.LBB1_5
# %bb.2:
	xor	ebp, ebp
	mov	r15, rcx
	mov	r13, rsi
	jmp	.LBB1_3
.LBB1_5:
	movabs	r9, 9223372036854775806
	and	r9, r8
	mov	qword ptr [rsp + 48], r9        # 8-byte Spill
	lea	rax, [rsi + rsi]
	mov	qword ptr [rsp + 40], rax       # 8-byte Spill
	lea	rax, [rcx + rcx]
	mov	qword ptr [rsp + 32], rax       # 8-byte Spill
	xor	ebp, ebp
	mov	r14, rdx
	mov	r12, rdi
	mov	r15, rcx
	mov	r13, rsi
	.p2align	4
.LBB1_6:                                # =>This Inner Loop Header: Depth=1
	mov	rdi, r12
	mov	rsi, r14
	mov	rdx, rbx
	call	memcpy@PLT
	lea	rdi, [r12 + r13]
	lea	rsi, [r14 + r15]
	mov	rdx, rbx
	call	memcpy@PLT
	add	rbp, 2
	add	r12, qword ptr [rsp + 40]       # 8-byte Folded Reload
	add	r14, qword ptr [rsp + 32]       # 8-byte Folded Reload
	cmp	qword ptr [rsp + 48], rbp       # 8-byte Folded Reload
	jne	.LBB1_6
.LBB1_3:
	test	byte ptr [rsp + 8], 1           # 1-byte Folded Reload
	mov	rsi, qword ptr [rsp + 24]       # 8-byte Reload
	mov	rdi, qword ptr [rsp + 16]       # 8-byte Reload
	jne	.LBB1_7
.LBB1_4:
	add	rsp, 56
	pop	rbx
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	pop	rbp
	ret
.LBB1_7:
	imul	r13, rbp
	add	rdi, r13
	imul	r15, rbp
	add	rsi, r15
	mov	rdx, rbx
	add	rsp, 56
	pop	rbx
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	pop	rbp
	jmp	memcpy@PLT                      # TAILCALL
.Lfunc_end1:
	.size	_Z12rows_runtimePSt4bytelPKS_lll, .Lfunc_end1-_Z12rows_runtimePSt4bytelPKS_lll
                                        # -- End function
	.globl	_Z11rows_fixed4PSt4bytelPKS_ll  # -- Begin function _Z11rows_fixed4PSt4bytelPKS_ll
	.p2align	4
	.type	_Z11rows_fixed4PSt4bytelPKS_ll,@function
_Z11rows_fixed4PSt4bytelPKS_ll:         # @_Z11rows_fixed4PSt4bytelPKS_ll
# %bb.0:
	test	r8, r8
	jle	.LBB2_9
# %bb.1:
	push	rbp
	push	r15
	push	r14
	push	r12
	push	rbx
	mov	eax, r8d
	and	eax, 3
	cmp	r8, 4
	jae	.LBB2_3
# %bb.2:
	xor	r9d, r9d
	jmp	.LBB2_5
.LBB2_3:
	movabs	r9, 9223372036854775804
	and	r8, r9
	lea	r10, [rsi + 2*rsi]
	lea	r11, [4*rsi]
	lea	rbx, [rcx + 2*rcx]
	lea	r14, [4*rcx]
	xor	r9d, r9d
	mov	r15, rdx
	mov	r12, rdi
	.p2align	4
.LBB2_4:                                # =>This Inner Loop Header: Depth=1
	mov	ebp, dword ptr [r15]
	mov	dword ptr [r12], ebp
	mov	ebp, dword ptr [r15 + rcx]
	mov	dword ptr [r12 + rsi], ebp
	mov	ebp, dword ptr [r15 + 2*rcx]
	mov	dword ptr [r12 + 2*rsi], ebp
	mov	ebp, dword ptr [r15 + rbx]
	mov	dword ptr [r12 + r10], ebp
	add	r9, 4
	add	r12, r11
	add	r15, r14
	cmp	r8, r9
	jne	.LBB2_4
.LBB2_5:
	test	rax, rax
	je	.LBB2_8
# %bb.6:
	mov	r8, r9
	imul	r8, rcx
	add	rdx, r8
	imul	r9, rsi
	add	rdi, r9
	.p2align	4
.LBB2_7:                                # =>This Inner Loop Header: Depth=1
	mov	r8d, dword ptr [rdx]
	mov	dword ptr [rdi], r8d
	add	rdx, rcx
	add	rdi, rsi
	dec	rax
	jne	.LBB2_7
.LBB2_8:
	pop	rbx
	pop	r12
	pop	r14
	pop	r15
	pop	rbp
.LBB2_9:
	ret
.Lfunc_end2:
	.size	_Z11rows_fixed4PSt4bytelPKS_ll, .Lfunc_end2-_Z11rows_fixed4PSt4bytelPKS_ll
                                        # -- End function
	.globl	_Z8pack_varPSt4bytePKS_lll      # -- Begin function _Z8pack_varPSt4bytePKS_lll
	.p2align	4
	.type	_Z8pack_varPSt4bytePKS_lll,@function
_Z8pack_varPSt4bytePKS_lll:             # @_Z8pack_varPSt4bytePKS_lll
# %bb.0:
	test	rdx, rdx
	jle	.LBB3_7
# %bb.1:
	push	rbp
	push	r15
	push	r14
	push	r13
	push	r12
	push	rbx
	push	rax
	mov	rbx, r8
	mov	r14, rcx
	mov	r13, rdx
	mov	r15, rsi
	mov	r12, rdi
	mov	ebp, r13d
	and	ebp, 3
	cmp	rdx, 4
	jb	.LBB3_4
# %bb.2:
	movabs	rax, 9223372036854775804
	and	r13, rax
	.p2align	4
.LBB3_3:                                # =>This Inner Loop Header: Depth=1
	mov	rdi, r12
	mov	rsi, r15
	mov	rdx, rbx
	call	memcpy@PLT
	add	r15, r14
	add	r12, rbx
	mov	rdi, r12
	mov	rsi, r15
	mov	rdx, rbx
	call	memcpy@PLT
	add	r15, r14
	add	r12, rbx
	mov	rdi, r12
	mov	rsi, r15
	mov	rdx, rbx
	call	memcpy@PLT
	add	r15, r14
	add	r12, rbx
	mov	rdi, r12
	mov	rsi, r15
	mov	rdx, rbx
	call	memcpy@PLT
	add	r15, r14
	add	r12, rbx
	add	r13, -4
	jne	.LBB3_3
.LBB3_4:
	test	rbp, rbp
	je	.LBB3_6
	.p2align	4
.LBB3_5:                                # =>This Inner Loop Header: Depth=1
	mov	rdi, r12
	mov	rsi, r15
	mov	rdx, rbx
	call	memcpy@PLT
	add	r15, r14
	add	r12, rbx
	dec	rbp
	jne	.LBB3_5
.LBB3_6:
	add	rsp, 8
	pop	rbx
	pop	r12
	pop	r13
	pop	r14
	pop	r15
	pop	rbp
.LBB3_7:
	ret
.Lfunc_end3:
	.size	_Z8pack_varPSt4bytePKS_lll, .Lfunc_end3-_Z8pack_varPSt4bytePKS_lll
                                        # -- End function
	.globl	_Z11pack_fixed4PSt4bytePKS_ll   # -- Begin function _Z11pack_fixed4PSt4bytePKS_ll
	.p2align	4
	.type	_Z11pack_fixed4PSt4bytePKS_ll,@function
_Z11pack_fixed4PSt4bytePKS_ll:          # @_Z11pack_fixed4PSt4bytePKS_ll
# %bb.0:
	test	rdx, rdx
	jle	.LBB4_7
# %bb.1:
	mov	eax, edx
	and	eax, 7
	cmp	rdx, 8
	jb	.LBB4_4
# %bb.2:
	movabs	r8, 9223372036854775800
	and	rdx, r8
	lea	r8, [rcx + rcx]
	.p2align	4
.LBB4_3:                                # =>This Inner Loop Header: Depth=1
	mov	r9d, dword ptr [rsi]
	mov	dword ptr [rdi], r9d
	mov	r9d, dword ptr [rsi + rcx]
	add	rsi, rcx
	mov	dword ptr [rdi + 4], r9d
	mov	r9d, dword ptr [rcx + rsi]
	add	rsi, rcx
	mov	dword ptr [rdi + 8], r9d
	mov	r9d, dword ptr [rcx + rsi]
	add	rsi, rcx
	mov	dword ptr [rdi + 12], r9d
	mov	r9d, dword ptr [rcx + rsi]
	add	rsi, rcx
	mov	dword ptr [rdi + 16], r9d
	mov	r9d, dword ptr [rcx + rsi]
	add	rsi, rcx
	mov	dword ptr [rdi + 20], r9d
	mov	r9d, dword ptr [rcx + rsi]
	add	rsi, rcx
	mov	dword ptr [rdi + 24], r9d
	mov	r9d, dword ptr [rcx + rsi]
	mov	dword ptr [rdi + 28], r9d
	add	rsi, r8
	add	rdi, 32
	add	rdx, -8
	jne	.LBB4_3
.LBB4_4:
	test	rax, rax
	je	.LBB4_7
# %bb.5:
	xor	edx, edx
	.p2align	4
.LBB4_6:                                # =>This Inner Loop Header: Depth=1
	mov	r8d, dword ptr [rsi]
	mov	dword ptr [rdi + 4*rdx], r8d
	add	rsi, rcx
	inc	rdx
	cmp	rax, rdx
	jne	.LBB4_6
.LBB4_7:
	ret
.Lfunc_end4:
	.size	_Z11pack_fixed4PSt4bytePKS_ll, .Lfunc_end4-_Z11pack_fixed4PSt4bytePKS_ll
                                        # -- End function
	.globl	_Z11pack_fixed8PSt4bytePKS_ll   # -- Begin function _Z11pack_fixed8PSt4bytePKS_ll
	.p2align	4
	.type	_Z11pack_fixed8PSt4bytePKS_ll,@function
_Z11pack_fixed8PSt4bytePKS_ll:          # @_Z11pack_fixed8PSt4bytePKS_ll
# %bb.0:
	test	rdx, rdx
	jle	.LBB5_7
# %bb.1:
	mov	eax, edx
	and	eax, 7
	cmp	rdx, 8
	jb	.LBB5_4
# %bb.2:
	movabs	r8, 9223372036854775800
	and	rdx, r8
	lea	r8, [rcx + rcx]
	.p2align	4
.LBB5_3:                                # =>This Inner Loop Header: Depth=1
	mov	r9, qword ptr [rsi]
	mov	qword ptr [rdi], r9
	mov	r9, qword ptr [rsi + rcx]
	add	rsi, rcx
	mov	qword ptr [rdi + 8], r9
	mov	r9, qword ptr [rcx + rsi]
	add	rsi, rcx
	mov	qword ptr [rdi + 16], r9
	mov	r9, qword ptr [rcx + rsi]
	add	rsi, rcx
	mov	qword ptr [rdi + 24], r9
	mov	r9, qword ptr [rcx + rsi]
	add	rsi, rcx
	mov	qword ptr [rdi + 32], r9
	mov	r9, qword ptr [rcx + rsi]
	add	rsi, rcx
	mov	qword ptr [rdi + 40], r9
	mov	r9, qword ptr [rcx + rsi]
	add	rsi, rcx
	mov	qword ptr [rdi + 48], r9
	mov	r9, qword ptr [rcx + rsi]
	mov	qword ptr [rdi + 56], r9
	add	rsi, r8
	add	rdi, 64
	add	rdx, -8
	jne	.LBB5_3
.LBB5_4:
	test	rax, rax
	je	.LBB5_7
# %bb.5:
	xor	edx, edx
	.p2align	4
.LBB5_6:                                # =>This Inner Loop Header: Depth=1
	mov	r8, qword ptr [rsi]
	mov	qword ptr [rdi + 8*rdx], r8
	add	rsi, rcx
	inc	rdx
	cmp	rax, rdx
	jne	.LBB5_6
.LBB5_7:
	ret
.Lfunc_end5:
	.size	_Z11pack_fixed8PSt4bytePKS_ll, .Lfunc_end5-_Z11pack_fixed8PSt4bytePKS_ll
                                        # -- End function
	.globl	_Z12pack_fixed12PSt4bytePKS_ll  # -- Begin function _Z12pack_fixed12PSt4bytePKS_ll
	.p2align	4
	.type	_Z12pack_fixed12PSt4bytePKS_ll,@function
_Z12pack_fixed12PSt4bytePKS_ll:         # @_Z12pack_fixed12PSt4bytePKS_ll
# %bb.0:
	test	rdx, rdx
	jle	.LBB6_7
# %bb.1:
	mov	eax, edx
	and	eax, 3
	cmp	rdx, 4
	jb	.LBB6_4
# %bb.2:
	movabs	r8, 9223372036854775804
	and	rdx, r8
	lea	r8, [rcx + rcx]
	.p2align	4
.LBB6_3:                                # =>This Inner Loop Header: Depth=1
	mov	r9d, dword ptr [rsi + 8]
	mov	dword ptr [rdi + 8], r9d
	mov	r9, qword ptr [rsi]
	mov	qword ptr [rdi], r9
	lea	r9, [rsi + rcx]
	mov	r10d, dword ptr [rsi + rcx + 8]
	mov	dword ptr [rdi + 20], r10d
	mov	rsi, qword ptr [rsi + rcx]
	mov	qword ptr [rdi + 12], rsi
	lea	rsi, [r9 + rcx]
	mov	r10d, dword ptr [rcx + r9 + 8]
	mov	dword ptr [rdi + 32], r10d
	mov	r9, qword ptr [rcx + r9]
	mov	qword ptr [rdi + 24], r9
	mov	r9, qword ptr [rcx + rsi]
	mov	qword ptr [rdi + 36], r9
	mov	r9d, dword ptr [rcx + rsi + 8]
	mov	dword ptr [rdi + 44], r9d
	add	rsi, r8
	add	rdi, 48
	add	rdx, -4
	jne	.LBB6_3
.LBB6_4:
	test	rax, rax
	je	.LBB6_7
# %bb.5:
	shl	eax, 2
	lea	rax, [rax + 2*rax]
	xor	edx, edx
	.p2align	4
.LBB6_6:                                # =>This Inner Loop Header: Depth=1
	mov	r8d, dword ptr [rsi + 8]
	mov	dword ptr [rdi + rdx + 8], r8d
	mov	r8, qword ptr [rsi]
	mov	qword ptr [rdi + rdx], r8
	add	rsi, rcx
	add	rdx, 12
	cmp	rax, rdx
	jne	.LBB6_6
.LBB6_7:
	ret
.Lfunc_end6:
	.size	_Z12pack_fixed12PSt4bytePKS_ll, .Lfunc_end6-_Z12pack_fixed12PSt4bytePKS_ll
                                        # -- End function
	.globl	_Z12pack_fixed16PSt4bytePKS_ll  # -- Begin function _Z12pack_fixed16PSt4bytePKS_ll
	.p2align	4
	.type	_Z12pack_fixed16PSt4bytePKS_ll,@function
_Z12pack_fixed16PSt4bytePKS_ll:         # @_Z12pack_fixed16PSt4bytePKS_ll
# %bb.0:
	test	rdx, rdx
	jle	.LBB7_7
# %bb.1:
	mov	eax, edx
	and	eax, 3
	cmp	rdx, 4
	jb	.LBB7_4
# %bb.2:
	movabs	r8, 9223372036854775804
	and	rdx, r8
	lea	r8, [rcx + rcx]
	.p2align	4
.LBB7_3:                                # =>This Inner Loop Header: Depth=1
	movups	xmm0, xmmword ptr [rsi]
	movups	xmmword ptr [rdi], xmm0
	movups	xmm0, xmmword ptr [rsi + rcx]
	add	rsi, rcx
	movups	xmmword ptr [rdi + 16], xmm0
	movups	xmm0, xmmword ptr [rcx + rsi]
	add	rsi, rcx
	movups	xmmword ptr [rdi + 32], xmm0
	movups	xmm0, xmmword ptr [rcx + rsi]
	movups	xmmword ptr [rdi + 48], xmm0
	add	rsi, r8
	add	rdi, 64
	add	rdx, -4
	jne	.LBB7_3
.LBB7_4:
	test	rax, rax
	je	.LBB7_7
# %bb.5:
	shl	eax, 4
	xor	edx, edx
	.p2align	4
.LBB7_6:                                # =>This Inner Loop Header: Depth=1
	movups	xmm0, xmmword ptr [rsi]
	movups	xmmword ptr [rdi + rdx], xmm0
	add	rsi, rcx
	add	rdx, 16
	cmp	rax, rdx
	jne	.LBB7_6
.LBB7_7:
	ret
.Lfunc_end7:
	.size	_Z12pack_fixed16PSt4bytePKS_ll, .Lfunc_end7-_Z12pack_fixed16PSt4bytePKS_ll
                                        # -- End function
	.globl	_Z12pack_fixed64PSt4bytePKS_ll  # -- Begin function _Z12pack_fixed64PSt4bytePKS_ll
	.p2align	4
	.type	_Z12pack_fixed64PSt4bytePKS_ll,@function
_Z12pack_fixed64PSt4bytePKS_ll:         # @_Z12pack_fixed64PSt4bytePKS_ll
# %bb.0:
	test	rdx, rdx
	jle	.LBB8_7
# %bb.1:
	mov	eax, edx
	and	eax, 3
	cmp	rdx, 4
	jb	.LBB8_4
# %bb.2:
	movabs	r8, 9223372036854775804
	and	rdx, r8
	lea	r8, [rcx + rcx]
	.p2align	4
.LBB8_3:                                # =>This Inner Loop Header: Depth=1
	movups	xmm0, xmmword ptr [rsi]
	movups	xmm1, xmmword ptr [rsi + 16]
	movups	xmm2, xmmword ptr [rsi + 32]
	movups	xmm3, xmmword ptr [rsi + 48]
	movups	xmmword ptr [rdi + 48], xmm3
	movups	xmmword ptr [rdi + 32], xmm2
	movups	xmmword ptr [rdi + 16], xmm1
	movups	xmmword ptr [rdi], xmm0
	lea	r9, [rsi + rcx]
	movups	xmm0, xmmword ptr [rsi + rcx]
	movups	xmm1, xmmword ptr [rsi + rcx + 16]
	movups	xmm2, xmmword ptr [rsi + rcx + 32]
	movups	xmm3, xmmword ptr [rsi + rcx + 48]
	movups	xmmword ptr [rdi + 112], xmm3
	movups	xmmword ptr [rdi + 96], xmm2
	movups	xmmword ptr [rdi + 80], xmm1
	movups	xmmword ptr [rdi + 64], xmm0
	lea	rsi, [r9 + rcx]
	movups	xmm0, xmmword ptr [rcx + r9]
	movups	xmm1, xmmword ptr [rcx + r9 + 16]
	movups	xmm2, xmmword ptr [rcx + r9 + 32]
	movups	xmm3, xmmword ptr [rcx + r9 + 48]
	movups	xmmword ptr [rdi + 176], xmm3
	movups	xmmword ptr [rdi + 160], xmm2
	movups	xmmword ptr [rdi + 144], xmm1
	movups	xmmword ptr [rdi + 128], xmm0
	movups	xmm0, xmmword ptr [rcx + rsi]
	movups	xmm1, xmmword ptr [rcx + rsi + 16]
	movups	xmm2, xmmword ptr [rcx + rsi + 32]
	movups	xmm3, xmmword ptr [rcx + rsi + 48]
	movups	xmmword ptr [rdi + 192], xmm0
	movups	xmmword ptr [rdi + 208], xmm1
	movups	xmmword ptr [rdi + 224], xmm2
	movups	xmmword ptr [rdi + 240], xmm3
	add	rsi, r8
	add	rdi, 256
	add	rdx, -4
	jne	.LBB8_3
.LBB8_4:
	test	rax, rax
	je	.LBB8_7
# %bb.5:
	shl	eax, 6
	xor	edx, edx
	.p2align	4
.LBB8_6:                                # =>This Inner Loop Header: Depth=1
	movups	xmm0, xmmword ptr [rsi]
	movups	xmm1, xmmword ptr [rsi + 16]
	movups	xmm2, xmmword ptr [rsi + 32]
	movups	xmm3, xmmword ptr [rsi + 48]
	movups	xmmword ptr [rdi + rdx + 48], xmm3
	movups	xmmword ptr [rdi + rdx + 32], xmm2
	movups	xmmword ptr [rdi + rdx + 16], xmm1
	movups	xmmword ptr [rdi + rdx], xmm0
	add	rsi, rcx
	add	rdx, 64
	cmp	rax, rdx
	jne	.LBB8_6
.LBB8_7:
	ret
.Lfunc_end8:
	.size	_Z12pack_fixed64PSt4bytePKS_ll, .Lfunc_end8-_Z12pack_fixed64PSt4bytePKS_ll
                                        # -- End function
	.section	".linker-options","e",@llvm_linker_options
	.ident	"clang version 20.1.8"
	.section	".note.GNU-stack","",@progbits
	.addrsig
