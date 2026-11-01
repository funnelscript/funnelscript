world Library {
  entity Counter {
    state total: int = 0;
    rule Increase on event Pulse { transition total = total + 1; }
  }
}
