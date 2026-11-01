world Broken {
  entity A {
    state n: int = 0;
    event Go(delta: float);
    rule R on event Go { transition n = n + payload.delta; }
  }
}