#!/usr/bin/env bash
# Runs every test/*.test.mo compiled to WASI under wasmtime. A test passes when it
# exits 0 AND prints at least one "count: <what> = <n>" line with no zero count:
# a test that examined nothing has failed. WASM_STACK=<bytes> runs every test under that wasm
# stack, as the substrate does with a small one.
# Attribution: Thebes Core Team. Licence: Apache 2.0.
set -u
cd "$(dirname "$0")/.."
MOC="${MOC:-/opt/moc-1.4.1/moc}"
SOURCES="$(mops sources)"
OUT="${TEST_OUT:-$(mktemp -d)}"
mkdir -p "$OUT"
fail=0; total=0
for t in test/${1:-*}.test.mo; do
  name="$(basename "$t" .test.mo)"; total=$((total+1))
  echo "=== $name"
  if ! "$MOC" -wasi-system-api $SOURCES -o "$OUT/$name.wasm" "$t" 2> "$OUT/$name.compile.log"; then
    echo "COMPILE FAILED: $name"; grep -v "warning" "$OUT/$name.compile.log" | head -20; fail=$((fail+1)); continue
  fi
  if ! wasmtime ${WASM_STACK:+-W max-wasm-stack=$WASM_STACK} "$OUT/$name.wasm" > "$OUT/$name.log" 2>&1; then
    echo "FAILED: $name"; tail -30 "$OUT/$name.log"; fail=$((fail+1)); continue
  fi
  grep -E '^(count:|FAIL|[A-Z]+ GREEN)' "$OUT/$name.log"
  if ! grep -Eq '^count: [^=]+ = [1-9][0-9]*$' "$OUT/$name.log"; then echo "FAILED: $name printed no count line"; fail=$((fail+1)); continue; fi
  if grep -Eq '^count: [^=]+ = 0$' "$OUT/$name.log"; then echo "FAILED: $name examined zero records"; fail=$((fail+1)); continue; fi
done
echo "tests: $total, failed: $fail  (logs in $OUT)"
[ "$fail" -eq 0 ]
