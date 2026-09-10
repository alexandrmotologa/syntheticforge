"""Field generation engine providing stochastic and deterministic value generators."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
import re
import string
import time
from typing import Any
import uuid

from faker import Faker

from syntheticforge.config import FieldConfig, FieldType


class FieldGenerator:
    """Generates synthetic values according to FieldConfig specifications."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._faker = Faker()
        if seed is not None:
            self._faker.seed_instance(seed)
        self._counters: dict[str, int] = {}

    def generate(
        self,
        field_name: str,
        config: FieldConfig,
        current_record: dict[str, Any] | None = None,
        base_timestamp: datetime | None = None,
    ) -> Any:
        """Generate a single field value based on its FieldConfig."""
        # Handle nullable probability
        if config.nullable and self._rng.random() < config.null_probability:
            return None

        t = config.type
        if t == FieldType.UUID:
            return str(uuid.UUID(int=self._rng.getrandbits(128), version=4))

        elif t == FieldType.ULID:
            return self._generate_ulid(base_timestamp)

        elif t == FieldType.INTEGER:
            min_val = int(config.min if config.min is not None else 1)
            max_val = int(config.max if config.max is not None else 1000)
            return self._rng.randint(min_val, max_val)

        elif t == FieldType.SEQUENCE:
            val = self._counters.get(field_name, config.start)
            self._counters[field_name] = val + config.step
            return val

        elif t == FieldType.DECIMAL:
            min_val = config.min if config.min is not None else 0.0
            max_val = config.max if config.max is not None else 100.0
            val = self._rng.uniform(min_val, max_val)
            return round(val, config.precision)

        elif t == FieldType.NAME:
            return self._faker.name()

        elif t == FieldType.EMAIL:
            if config.domain:
                user = self._faker.user_name()
                return f"{user}@{config.domain}"
            return self._faker.email()

        elif t == FieldType.CREDIT_CARD:
            return self._generate_luhn_credit_card()

        elif t == FieldType.TIMESTAMP:
            return self._generate_timestamp(config, base_timestamp)

        elif t == FieldType.ENUM:
            weights = config.weights if config.weights else None
            return self._rng.choices(config.values, weights=weights, k=1)[0]

        elif t == FieldType.REGEX:
            return self._generate_from_regex(config.pattern or "[A-Z0-9]{8}")

        elif t == FieldType.TEMPLATE:
            fmt = config.format or "{id}"
            rec = current_record or {}
            try:
                return fmt.format(**rec)
            except KeyError:
                return fmt

        return None

    def _generate_ulid(self, base_timestamp: datetime | None = None) -> str:
        """Generate a 26-character sortable ULID string."""
        now = base_timestamp or datetime.now(timezone.utc)
        millis = int(now.timestamp() * 1000)
        # Crockford's Base32 alphabet
        crockford = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
        # 10 chars timestamp
        time_chars = []
        for _ in range(10):
            time_chars.append(crockford[millis % 32])
            millis //= 32
        time_part = "".join(reversed(time_chars))

        # 16 chars random
        rand_part = "".join(self._rng.choices(crockford, k=16))
        return time_part + rand_part

    def _generate_luhn_credit_card(self) -> str:
        """Generate a 16-digit Luhn-valid card number."""
        # Prefix 4 for Visa or 51-55 for Mastercard
        prefix = self._rng.choice(["4", "51", "52", "53", "54", "55"])
        digits = [int(d) for d in prefix]
        while len(digits) < 15:
            digits.append(self._rng.randint(0, 9))

        # Calculate Luhn check digit
        checksum = 0
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 0:
                doubled = d * 2
                checksum += doubled - 9 if doubled > 9 else doubled
            else:
                checksum += d

        check_digit = (10 - (checksum % 10)) % 10
        digits.append(check_digit)
        return "".join(str(d) for d in digits)

    def _generate_timestamp(
        self, config: FieldConfig, base_timestamp: datetime | None = None
    ) -> str:
        """Generate an ISO 8601 formatted timestamp within past/future window."""
        ref = base_timestamp or datetime.now(timezone.utc)
        past_secs = config.past_days * 86400
        future_secs = config.future_days * 86400

        offset_secs = self._rng.uniform(-past_secs, future_secs)
        dt = ref + timedelta(seconds=offset_secs)
        return dt.isoformat()

    def _generate_from_regex(self, pattern: str) -> str:
        """Basic regex string generator supporting common patterns."""
        # Simple rule-based expansion for common schema patterns
        out: list[str] = []
        i = 0
        while i < len(pattern):
            if pattern[i : i + 2] == "\\*":
                out.append("*")
                i += 2
                continue
            if pattern[i] == "\\":
                i += 1
                if i < len(pattern):
                    out.append(pattern[i])
                    i += 1
                continue

            m = re.match(r"\[([A-Za-z0-9_-]+)\]\{(\d+)\}", pattern[i:])
            if m:
                charset_spec, count_str = m.group(1), m.group(2)
                count = int(count_str)
                chars = self._expand_charset(charset_spec)
                out.extend(self._rng.choices(chars, k=count))
                i += m.end()
                continue

            m2 = re.match(r"\[([A-Za-z0-9_-]+)\]", pattern[i:])
            if m2:
                chars = self._expand_charset(m2.group(1))
                out.append(self._rng.choice(chars))
                i += m2.end()
                continue

            out.append(pattern[i])
            i += 1

        return "".join(out)

    def _expand_charset(self, spec: str) -> str:
        res = []
        if "A-Z" in spec:
            res.append(string.ascii_uppercase)
        if "a-z" in spec:
            res.append(string.ascii_lowercase)
        if "0-9" in spec:
            res.append(string.digits)
        # Any remaining literal chars
        clean = spec.replace("A-Z", "").replace("a-z", "").replace("0-9", "")
        if clean:
            res.append(clean)
        return "".join(res) or string.ascii_letters
