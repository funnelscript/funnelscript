world Zero { entity A {
  state numerator: float = 1.0;
  state divisor: float = 0.0;
  rule Divide on event Go { transition numerator = numerator / divisor; }
} }
