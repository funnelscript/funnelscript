world Arithmetic {
  entity Values {
    state plus: int = 2;
    state minus: int = 8;
    state times: int = 3;
    state fraction: float = 9.0;
    state divisor: float = 3.0;
    state quotient: float = 0.0;
    rule Compute on event Calc {
      transition plus = plus + 5;
      transition minus = minus - 2;
      transition times = times * 4;
      transition quotient = fraction / divisor;
    }
  }
}
