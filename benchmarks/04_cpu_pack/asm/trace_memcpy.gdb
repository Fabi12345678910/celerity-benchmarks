set pagination off
set disassembly-flavor intel
break *copy_one
run
continue
set $ret = *(void**)$sp
set $count = 0
while $pc != $ret
  x/i $pc
  stepi
  set $count = $count + 1
end
printf "instructions executed: %d\n", $count
