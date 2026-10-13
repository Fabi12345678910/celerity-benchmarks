set pagination off
break *measured
run
set $ret = *(void**)$sp
set $count = 0
while $pc != $ret
  stepi
  set $count = $count + 1
end
printf "instructions executed: %d\n", $count
