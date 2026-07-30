from dataclasses import dataclass
from typing import Dict, Tuple


MASK_48 = (1 << 48) - 1
MASK_80 = (1 << 80) - 1


DTYPE_NAMES: Dict[int, str] = {
    0: "int8",
    1: "uint8",
    2: "int4",
    3: "uint4",
    4: "int2",
    5: "uint2",
    6: "int8_equivalent",
    7: "uint8_equivalent",
}


DTYPE_LIMITS: Dict[int, Tuple[int, int]] = {
    0: (-128, 127),
    1: (0, 255),
    2: (-8, 7),
    3: (0, 15),
    4: (-2, 1),
    5: (0, 3),
    6: (-128, 127),
    7: (0, 255),
}


@dataclass(frozen=True)
class QuantizerResult:
    """Expected output and useful internal values for one input vector."""

    output: int
    overflow: bool

    dtype_name: str
    exponent: int
    significand: int
    scaled_data: int

    shift_amount: int
    truncated_data: int
    retained_lsb: int
    guard_bit: int
    sticky_bit: bool
    round_up: bool
    rounded_data: int

    zero_point_value: int
    after_zero_point: int
    early_overflow: bool
    clipped_value: int


def to_signed(value: int, width: int) -> int:
    """Interpret value as a signed two's-complement number."""
    if width <= 0:
        raise ValueError("width must be positive")

    value &= (1 << width) - 1
    sign_bit = 1 << (width - 1)
    return value - (1 << width) if value & sign_bit else value


class QuantizerGoldenModel:

    def quantize(
        self,
        i_data: int,
        i_scale: int,
        i_zero_point: int,
        i_target_dtype: int,
    ) -> QuantizerResult:
        """Evaluate one quantizer input vector.

        Args:
            i_data: Signed 23-bit input value.
            i_scale: Raw 32-bit scale bit pattern.
            i_zero_point: Raw 8-bit zero point or an equivalent negative value.
            i_target_dtype: Dtype code 0 through 7.

        Returns:
            A QuantizerResult containing the expected output, overflow,
            and intermediate values useful for debugging failures.
        """
        if i_target_dtype not in DTYPE_LIMITS:
            raise ValueError(
                f"i_target_dtype must be in the range 0..7, got {i_target_dtype}"
            )

        data = to_signed(i_data, 23)
        scale = i_scale & 0xFFFFFFFF
        zero_point_raw = i_zero_point & 0xFF
        dtype = i_target_dtype

        # Stage 1: scale decode and signed multiplication
        exponent = (scale >> 23) & 0xFF
        mantissa = scale & 0x7FFFFF

        # Mirrors $signed({1'b0, 1'b1, i_scale[22:0]}).
        significand = (1 << 23) | mantissa
        scaled_data = to_signed(data * significand, 48)

        shift_amount = 0
        truncated_data = 0
        retained_lsb = 0
        guard_bit = 0
        sticky_bit = False
        round_up = False


        # Stage 2: exponent shift and round-to-nearest-even
        if scaled_data == 0:
            rounded_data = 0

        elif exponent < 102:
            rounded_data = 0

        elif exponent <= 134:
            shift_amount = 150 - exponent

            # Mirrors the signed 80-bit expression: $signed({scaled_data, 32'sd0}) >>> shift_amount
            extended_before_shift = to_signed(
                (scaled_data & MASK_48) << 32,
                80,
            )
            extended_after_shift = extended_before_shift >> shift_amount
            extended_bits = extended_after_shift & MASK_80

            truncated_data = to_signed(
                (extended_bits >> 32) & MASK_48,
                48,
            )
            retained_lsb = (extended_bits >> 32) & 0x1
            guard_bit = (extended_bits >> 31) & 0x1
            sticky_bit = bool(extended_bits & ((1 << 31) - 1))

            # Mirrors: extended_scaled_data[31] && (extended_scaled_data[32] || extended_scaled_data[30:0])
            round_up = bool(
                guard_bit and (retained_lsb or sticky_bit)
            )
            rounded_data = to_signed(
                truncated_data + int(round_up),
                48,
            )

        else:
            # Mirrors {(scaled_data[47]), {47{(!scaled_data[47])}}}.
            rounded_data = (
                -(1 << 47) if scaled_data < 0 else (1 << 47) - 1
            )

        early_overflow = bool(scaled_data != 0 and exponent > 134)


        # Stage 3: zero-point addition
        if dtype & 0x1:
            zero_point_value = zero_point_raw
        else:
            zero_point_value = to_signed(zero_point_raw, 8)

        if early_overflow:
            # RTL bypasses the zero point on early overflow.
            after_zero_point = rounded_data
        else:
            after_zero_point = to_signed(
                rounded_data + zero_point_value,
                48,
            )


        # Stage 4: dtype saturation and overflow generation
        minimum, maximum = DTYPE_LIMITS[dtype]

        if after_zero_point > maximum:
            clipped_value = maximum
        elif after_zero_point < minimum:
            clipped_value = minimum
        else:
            clipped_value = after_zero_point

        overflow = bool(
            early_overflow
            or after_zero_point > maximum
            or after_zero_point < minimum
        )

        return QuantizerResult(
            output=clipped_value & 0xFF,
            overflow=overflow,
            dtype_name=DTYPE_NAMES[dtype],
            exponent=exponent,
            significand=significand,
            scaled_data=scaled_data,
            shift_amount=shift_amount,
            truncated_data=truncated_data,
            retained_lsb=retained_lsb,
            guard_bit=guard_bit,
            sticky_bit=sticky_bit,
            round_up=round_up,
            rounded_data=rounded_data,
            zero_point_value=zero_point_value,
            after_zero_point=after_zero_point,
            early_overflow=early_overflow,
            clipped_value=clipped_value,
        )


def quantize(
    i_data: int,
    i_scale: int,
    i_zero_point: int,
    i_target_dtype: int,
) -> QuantizerResult:
    """Convenience wrapper around QuantizerGoldenModel.quantize."""
    return QuantizerGoldenModel().quantize(
        i_data=i_data,
        i_scale=i_scale,
        i_zero_point=i_zero_point,
        i_target_dtype=i_target_dtype,
    )


if __name__ == "__main__":
    model = QuantizerGoldenModel()

    examples = (
        ("normal positive", 162574, 0x391C68A3, 41, 0),
        ("negative zero point", 147, 0x3E7182C0, -12, 0),
        ("negative data", -9, 0x415AAAAB, 108, 0),
        ("+0.5 tie", 8, 0x3D800000, 0, 0),
        ("+1.5 tie", 4, 0x3EC00000, 0, 0),
        ("negative early overflow", -1, 0x43800000, 124, 0),
    )

    for name, data, scale, zero_point, dtype in examples:
        result = model.quantize(data, scale, zero_point, dtype)
        print(
            f"{name:25s} "
            f"output=0x{result.output:02X} "
            f"overflow={int(result.overflow)} "
            f"rounded={result.rounded_data} "
            f"after_zp={result.after_zero_point}"
        )
