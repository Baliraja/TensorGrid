"""
Golden model for int_MAC.

Mirrors the DUT's two always_ff blocks as plain Python state, updated once
per step() call (call this once per posedge clk, after applying that
cycle's i_valid/i_a/i_b, mirroring how the RTL samples inputs on the edge).

Nonblocking-assignment ordering is preserved deliberately:
  - accumulation this cycle uses the OLD valid_0 / OLD overflow
  - product / valid_0 / result_reg / overflow are all "committed" together
    at the end of step(), like <= updates land after the whole block
    evaluates.
"""

def sign_extend(value: int, bits: int) -> int:
    """Interpret the lower `bits` bits of value as a signed integer."""
    value &= (1 << bits) - 1
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


class IntMacGolden:
    def __init__(self):
        self.reset()

    def reset(self):
        self.product = 0      # signed 18-bit
        self.valid_0 = 0
        self.result_reg = 0   # signed 23-bit
        self.overflow = 0
        self.o_valid = 0

    def step(self, i_valid: int, i_a: int, i_b: int):
        """
        Advance golden state by exactly one clock edge.
        i_a, i_b are taken as signed 9-bit values (raw int, e.g. -256..255
        or the two's-complement 9-bit encoding -- both work since we
        sign_extend from the low 9 bits).
        """
        a9 = sign_extend(i_a, 9)
        b9 = sign_extend(i_b, 9)

        # ---- compute "next" values based on OLD state (combinational logic
        #      + nonblocking read-before-write semantics) ----
        next_product = self.product
        if i_valid:
            next_product = sign_extend(a9 * b9, 18)

        next_result_reg = self.result_reg
        next_overflow = self.overflow

        if self.valid_0 and not self.overflow:
            extended = sign_extend(self.result_reg, 23) + sign_extend(self.product, 18)
            extended24 = sign_extend(extended, 24)  # extended_result[23:0]
            bit23 = (extended24 >> 23) & 1
            bit22 = (extended24 >> 22) & 1
            ovf = 1 if bit23 != bit22 else 0

            next_result_reg = sign_extend(extended24 & 0x7FFFFF, 23)
            next_overflow = ovf

        next_o_valid = 1 if (self.valid_0 and not self.overflow) else 0

        next_valid_0 = 1 if i_valid else 0

        # ---- commit all updates together (mirrors <= ) ----
        self.product = next_product
        self.result_reg = next_result_reg
        self.overflow = next_overflow
        self.o_valid = next_o_valid
        self.valid_0 = next_valid_0

    # Convenience accessors matching DUT port names
    @property
    def o_result(self):
        return self.result_reg & 0x7FFFFF  # unsigned 23-bit view, like Verilog output

    @property
    def o_overflow(self):
        return self.overflow
