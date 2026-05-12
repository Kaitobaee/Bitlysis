/**
 * WASM core: byte validation only (CSV head). No statistical analysis.
 * Text decode + row split stay in TS (worker) to keep bundle/runtime small.
 */

/** 1 if any byte is 0 in [ptr, ptr+len), else 0. */
export function has_null_byte(ptr: usize, len: i32): i32 {
  for (let i: i32 = 0; i < len; i++) {
    if (load<u8>(ptr + usize(i)) == 0) {
      return 1;
    }
  }
  return 0;
}
